#!/usr/bin/env python3
"""机验：校验锚点真实性、JSON 清单结构、值域、澄清引用与数量守恒。

用法：
  python3 verify_citation.py --docs <原文根> [--docs <根2>] \
      (--index <资源索引> | --tp <TP功能文件>... | --tc <TC功能文件>...) \
      [--clar <澄清表>] [--out citation-result*.json]

  --docs   原文检索根目录，可重复
  --index  scope/resources-index.md，验索引锚点
  --tp     TP 功能文件（output/tp/tp-{功能号}.json），可重复传本批多个功能
  --tc     TC 功能文件（output/tc/tc-{功能号}.json），可重复传本批多个功能；
           与 --tp 按文件名功能号配对做交叉校验，编号唯一性按文件内判定
  --clar   state/clarifications.md，校验 C 编号引用
  --out    结果 JSON 落盘路径；省略则只打印到 stdout

退出码：0 无失败 / 1 有失败 / 2 用法或致命错误。
输出字段：ok、summary、failures、warnings、entry_lines（功能文件→编号→起始-结束行区间，
供语义验与复检按行段精准读取，免整文件回读）。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib_citation import (
    CLAR_REF,
    anchors_of,
    as_list,
    broken_table_rows,
    check_anchor,
    json_list_with_lines,
    norm,
    parse_md_tables,
    table_fragment_count,
    table_with_columns,
)

TP_REQUIRED = ["编号", "关联业务功能", "测试点名称", "类型", "测试维度", "所属小类", "用例展开重点", "依据类型", "澄清依据", "出处锚点"]
TC_REQUIRED = ["编号", "关联业务功能", "关联TP", "用例名称", "用例类型", "测试方法", "前置条件", "测试数据", "操作步骤", "预期结果", "依据类型", "澄清依据", "出处锚点"]
# JSON 清单顶层条目数组的键名（与 test-point-workflow / test-case-workflow【清单结构】一致）
TP_LIST_KEY = "测试点"
TC_LIST_KEY = "测试用例"
CLAR_REQUIRED = ["编号", "来源", "问题", "影响面", "默认建议", "答复", "状态"]
OUT_NAME = re.compile(r"^citation-result.*\.json$")
INDEX_ANCHOR_LINE = re.compile(r'^\s*[-*]\s*锚点\s*[:：]\s*(.+)$')
# 功能文件命名约定 tp-{功能号}.json / tc-{功能号}.json，取末段横线分隔的功能号作 TP↔TC 配对键
FUNC_TAG = re.compile(r"[-_]([^-_./\\]+)\.json$")


def file_tag(path):
    """从文件名提取功能号（tp-F01.json → F01）；不匹配时退回文件名主干，保证配对仍可用。"""
    base = os.path.basename(path)
    m = FUNC_TAG.search(base)
    return m.group(1) if m else os.path.splitext(base)[0]

# 测试维度 → 《测试维度定义》「二、测试维度明细」合法小类集（单值；维度-小类组合合法性机验依据）
TP_DIMENSIONS = {
    "基础功能": {"功能正确性", "字段校验", "业务规则", "异常与错误处理"},
    "业务流程": {"主流程", "分支流程", "状态流转", "流程衔接与回退"},
    "界面与体验（UI/UX）": {"布局与适配", "元素交互", "文案与多语言", "视觉与易用性"},
    "数据校验": {"数据正确性", "数据一致性", "数据隔离", "数据存储与持久化"},
    "权限控制": {"身份认证", "功能权限", "数据权限", "操作审计", "越权操作"},
    "接口 API 测试": {"接口契约", "参数校验", "业务逻辑", "异常处理"},
    "性能": {"响应速度", "并发正确性"},
    "安全": {"防攻击", "防泄露"},
    "兼容性与多端": {"环境与设备", "多端同步"},
    "可靠性与稳定性": {"故障恢复", "健壮性"},
}
TP_TYPES = {"功能级", "场景级"}
# 测试方法六枚举（《通用测试方法论》「七、方法选型决策指南」，单值白名单）
TC_METHODS = {"等价类+边界值", "决策表", "状态迁移", "场景法", "正交实验", "错误推测"}
# 依据类型二分：原文依据=锚点/澄清直接支撑；方法论补充=按四份原文知识链该维度/小类/关注点发散补测试内容，对象仍须有原文锚点
BASIS_TYPES = {"原文依据", "方法论补充"}

def load_rows(path, required, kind):
    if not path:
        return None, []
    if not os.path.isfile(path):
        fatal(["{} 文件不存在：{}".format(kind, path)])
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.strip():
        fatal(["{} 文件为空：{}".format(kind, path)])
    header, rows = table_with_columns(text, required)
    if header is None:
        fatal(["{} 表头缺少必需列，需要：{}".format(kind, "、".join(required))])
    warns = [
        {
            "record": "{} 表格第 {} 行".format(kind, ln),
            "reason": "表格行以 | 开头但未以 | 结尾——疑似单元格内真实换行打断行（该行已被解析跳过）；单元格内换行应使用 <br>",
        }
        for ln, _c in broken_table_rows(text)
    ]
    matched = sum(1 for h, _ in parse_md_tables(text) if all(col in h for col in required))
    frag = table_fragment_count(text)
    if frag > matched:
        warns.append(
            {
                "record": kind + " 表格结构",
                "reason": "文件解析出 {} 个表格片段，其中 {} 个含必需列——其余 {} 个片段的数据行未被读取（疑似断行后的孤立片段，应修复断行并整表重排）".format(frag, matched, frag - matched),
            }
        )
    return rows, warns


def load_json_rows(path, required, kind, list_key):
    """读取 JSON 清单（TP/TC 产物），结构非法即致命错误；条目缺字段由后续逐字段检查兜底。
    返回 (条目数组, 行区间表[(编号, 起, 止)])。"""
    if not path:
        return None, []
    if not os.path.isfile(path):
        fatal(["{} 文件不存在：{}".format(kind, path)])
    rows, marks, err = json_list_with_lines(path, list_key)
    if err:
        fatal(["{} {}：{}".format(kind, err, path)])
    if rows and not all(col in rows[0] for col in required):
        fatal(["{} 条目缺少必需字段，需要：{}".format(kind, "、".join(required))])
    return rows, marks or []


def dup_field(value):
    """重复检测键值归一：列表按序拼接，字符串折叠空白。"""
    if isinstance(value, list):
        return norm("|".join(str(v) for v in value))
    return norm(value)


def fatal(messages):
    payload = {
        "ok": False,
        "summary": {"failures": 0, "warnings": 0, "fatal": True},
        "failures": [],
        "warnings": [],
        "fatal_messages": messages,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(2)


def load_index_anchors(path):
    if not path:
        return []
    if not os.path.isfile(path):
        fatal(["resources-index 文件不存在：{}".format(path)])
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.strip():
        fatal(["resources-index 文件为空：{}".format(path)])
    anchors = []
    for line in text.splitlines():
        m = INDEX_ANCHOR_LINE.match(line)
        if m:
            anchors.extend(anchors_of(m.group(1)))
    if not anchors:
        fatal(["resources-index 未解析到任何锚点（格式应为 `- 锚点：文件名:起始行-结束行 => \"摘抄\"`）"])
    return anchors


def check_clar_ref(value, clar_set, record, failures, has_clar):
    # 多值：JSON 清单为数组，每项一个编号；空数组即无澄清依据
    for seg in as_list(value):
        if not CLAR_REF.match(seg):
            failures.append({"record": record, "field": "澄清依据", "anchor": seg, "reason": "澄清依据格式非法（数组每项应为 C-编号 或 C-编号(默认)）"})
            continue
        cid = CLAR_REF.match(seg).group(1)
        if has_clar and cid not in clar_set:
            failures.append({"record": record, "field": "澄清依据", "anchor": seg, "reason": "澄清编号 {} 在 clarifications.md 中不存在".format(cid)})


def check_basis_type(row, record, failures, summary, counter_key):
    basis = (row.get("依据类型") or "").strip()
    if basis not in BASIS_TYPES:
        failures.append({"record": record, "field": "依据类型", "anchor": basis or "(空)", "reason": "依据类型非法（仅 原文依据/方法论补充；两类均须带证明对象存在的原文锚点）"})
        return
    if basis == "方法论补充":
        summary[counter_key] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="append", required=True, help="原文检索根目录，可重复")
    ap.add_argument("--tp", action="append", help="TP 功能文件路径（tp-F{编号}.json），可重复")
    ap.add_argument("--tc", action="append", help="TC 功能文件路径（tc-F{编号}.json），可重复")
    ap.add_argument("--index", help="scope/resources-index.md 路径")
    ap.add_argument("--clar", help="state/clarifications.md 路径")
    ap.add_argument("--out", help="结果 JSON 输出路径（文件名须为 citation-result*.json）")
    args = ap.parse_args()

    if args.out and not OUT_NAME.match(os.path.basename(args.out)):
        fatal(["--out 文件名必须匹配 citation-result*.json，收到：{}".format(os.path.basename(args.out))])

    if not args.tp and not args.tc and not args.index:
        fatal(["至少提供 --tp / --tc / --index 之一"])

    docs = args.docs

    failures = []
    warnings = []
    summary = {"index_anchors": 0, "tp_rows": 0, "tc_rows": 0, "tp_methodology": 0, "tc_methodology": 0, "checks": 0, "failures": 0, "warnings": 0}

    # 功能标识 → {TP 编号: 条目信息}；编号按功能文件独立，跨文件重复合法
    tp_index = {}
    covered = set()  # 已有直属用例的 (功能标识, TP 编号)
    entry_lines = {}  # 功能文件名 → {编号: "起-止"}，供语义验与复检按行段读取

    if args.index:
        idx_anchors = load_index_anchors(args.index)
        summary["index_anchors"] = len(idx_anchors)
        for a in idx_anchors:
            summary["checks"] += 1
            reason = check_anchor(a, docs)
            if reason:
                failures.append({"record": "resources-index", "field": "锚点", "anchor": a, "reason": reason})

    clar_set = set()
    has_clar = False
    if args.clar:
        crows, w = load_rows(args.clar, CLAR_REQUIRED, "clarifications")
        warnings.extend(w)
        if crows is not None:
            has_clar = True
            for r in crows:
                cid = (r.get("编号") or "").strip()
                if cid:
                    clar_set.add(cid)

    if args.tp:
        for path in args.tp:
            tag = file_tag(path)
            fname = os.path.basename(path)
            tp_rows, marks = load_json_rows(path, TP_REQUIRED, "TP清单", TP_LIST_KEY)
            summary["tp_rows"] += len(tp_rows)
            entry_lines[fname] = {tid: "{}-{}".format(s, e) for tid, s, e in marks if tid}
            idx = tp_index.setdefault(tag, {})
            seen = set()  # 编号唯一性按文件内判定，跨功能文件重复合法
            for r in tp_rows:
                tid = (r.get("编号") or "").strip()
                record = "{} {}".format(fname, tid) if tid else "{} (空编号)".format(fname)
                if not re.fullmatch(r"TP-\d+", tid):
                    failures.append({"record": record, "field": "编号", "anchor": "-", "reason": "TP 编号格式非法（应为 TP-数字）"})
                    continue
                if tid in seen:
                    failures.append({"record": record, "field": "编号", "anchor": "-", "reason": "TP 编号在本文件内重复（文件内永久唯一，不得复用）"})
                    continue
                seen.add(tid)
                idx[tid] = {"name": (r.get("测试点名称") or "").strip(), "func": (r.get("关联业务功能") or "").strip(), "tc_count": 0, "record": record}
                anc = [a for a in anchors_of(r.get("出处锚点")) if a not in ("-", "")]
                if not anc:
                    failures.append({"record": record, "field": "出处锚点", "anchor": "-", "reason": "锚点为空（每条 TP 须有证明对象存在的原文锚点；方法论补充条目同样不得虚构字段/功能）"})
                for a in anc:
                    summary["checks"] += 1
                    reason = check_anchor(a, docs)
                    if reason:
                        failures.append({"record": record, "field": "出处锚点", "anchor": a, "reason": reason})
                check_basis_type(r, record, failures, summary, "tp_methodology")
                check_clar_ref(r.get("澄清依据"), clar_set, record, failures, has_clar)
                dim = (r.get("测试维度") or "").strip()
                sub = (r.get("所属小类") or "").strip()
                if dim not in TP_DIMENSIONS:
                    failures.append({"record": record, "field": "测试维度", "anchor": dim or "(空)", "reason": "测试维度非法（须为《测试维度定义》「一、大类与测试维度总览」维度枚举，单值）"})
                elif not sub:
                    failures.append({"record": record, "field": "所属小类", "anchor": "(空)", "reason": "所属小类为空（须填写小类层，单值）"})
                elif sub not in TP_DIMENSIONS[dim]:
                    failures.append({"record": record, "field": "所属小类", "anchor": sub, "reason": "所属小类 {} 不属于测试维度 {} 的合法小类集".format(sub, dim)})
                tp_type = (r.get("类型") or "").strip()
                if tp_type not in TP_TYPES:
                    failures.append({"record": record, "field": "类型", "anchor": tp_type or "(空)", "reason": "类型非法（仅 功能级/场景级）"})
                focus = as_list(r.get("用例展开重点"))
                if not focus:
                    failures.append({"record": record, "field": "用例展开重点", "anchor": "-", "reason": "用例展开重点为空（须填写可独立判定的展开分支；项数仅作展开充分性建议，见 test-point-workflow「落盘模板」）"})

    if args.tc:
        # TC 关联校验依赖同功能标识的 TP 文件，缺对即用法错误
        if not args.tp:
            fatal(["TC 机验须同时传入对应 TP 功能文件（--tp）以校验关联与数量守恒"])
        missing = sorted({file_tag(p) for p in args.tc} - set(tp_index))
        if missing:
            fatal(["以下 TC 文件缺少同功能标识的 TP 文件，请一并传入 --tp：{}".format("、".join(missing))])
        for path in args.tc:
            tag = file_tag(path)
            fname = os.path.basename(path)
            idx = tp_index[tag]
            tc_rows, marks = load_json_rows(path, TC_REQUIRED, "TC清单", TC_LIST_KEY)
            summary["tc_rows"] += len(tc_rows)
            entry_lines[fname] = {tid: "{}-{}".format(s, e) for tid, s, e in marks if tid}
            seen = set()  # 编号唯一性按文件内判定
            dup_map = {}  # (关联TP, 数据, 步骤, 预期) → [编号]，四要素全同即重复
            for r in tc_rows:
                tcid = (r.get("编号") or "").strip()
                record = "{} {}".format(fname, tcid) if tcid else "{} (空编号)".format(fname)
                if not re.fullmatch(r"TC-\d+", tcid):
                    failures.append({"record": record, "field": "编号", "anchor": "-", "reason": "TC 编号格式非法（应为 TC-数字）"})
                    continue
                if tcid in seen:
                    failures.append({"record": record, "field": "编号", "anchor": "-", "reason": "TC 编号在本文件内重复（文件内永久唯一，不得复用）"})
                    continue
                seen.add(tcid)
                ref_raw = (r.get("关联TP") or "").strip()
                ref, _, name_seg = ref_raw.partition(" ")
                ref = ref.strip()
                name_seg = name_seg.strip()
                if not re.fullmatch(r"TP-\d+", ref):
                    failures.append({"record": record, "field": "关联TP", "anchor": ref_raw or "(空)", "reason": "关联TP 编号段格式非法（应为 TP-数字，第一个空格分隔编号与名称）"})
                elif ref not in idx:
                    failures.append({"record": record, "field": "关联TP", "anchor": ref, "reason": "关联TP {} 在功能 {} 的 TP 文件中不存在（TC 只能关联同功能 TP 文件内的编号）".format(ref, tag)})
                else:
                    entry = idx[ref]
                    covered.add((tag, ref))
                    entry["tc_count"] += 1
                    if not name_seg:
                        failures.append({"record": record, "field": "关联TP", "anchor": ref_raw, "reason": "关联TP 缺名称段（应为 编号+名称 双信息，第一个空格分隔）"})
                    elif entry["name"] != name_seg:
                        failures.append({"record": record, "field": "关联TP", "anchor": name_seg, "reason": "关联TP 名称段与 TP 文件中 {} 的测试点名称不一致".format(ref)})
                    tp_func = (r.get("关联业务功能") or "").strip()
                    if tp_func != entry["func"]:
                        failures.append({"record": record, "field": "关联业务功能", "anchor": tp_func, "reason": "关联业务功能与主 TP {} 的关联业务功能不一致".format(ref)})
                m = (r.get("测试方法") or "").strip()
                if m not in TC_METHODS:
                    failures.append({"record": record, "field": "测试方法", "anchor": m or "(空)", "reason": "测试方法非法（六枚举：等价类+边界值/决策表/状态迁移/场景法/正交实验/错误推测，单值）"})
                anc = [a for a in anchors_of(r.get("出处锚点")) if a not in ("-", "")]
                if not anc:
                    failures.append({"record": record, "field": "出处锚点", "anchor": "-", "reason": "锚点为空（每条 TC 须有证明对象存在的原文锚点；方法论补充条目同样不得虚构字段/功能）"})
                for a in anc:
                    summary["checks"] += 1
                    reason = check_anchor(a, docs)
                    if reason:
                        failures.append({"record": record, "field": "出处锚点", "anchor": a, "reason": reason})
                check_basis_type(r, record, failures, summary, "tc_methodology")
                check_clar_ref(r.get("澄清依据"), clar_set, record, failures, has_clar)
                if re.fullmatch(r"TP-\d+", ref):
                    dup_key = (ref, dup_field(r.get("测试数据")), dup_field(r.get("操作步骤")), dup_field(r.get("预期结果")))
                    dup_map.setdefault(dup_key, []).append(tcid)
            for _key, ids in sorted(dup_map.items()):
                if len(ids) > 1:
                    failures.append({
                        "record": "{} {}".format(fname, "、".join(ids)),
                        "field": "用例重复",
                        "anchor": _key[0],
                        "reason": "关联TP/测试数据/操作步骤/预期结果四要素全同——保留一条，其余改为该 TP 独立分支（同值改名、伪边界等硬凑仍属语义检）",
                    })

    if args.tc:
        for tag in sorted(tp_index):
            for tid in sorted(tp_index[tag]):
                if (tag, tid) not in covered:
                    warnings.append({"record": tp_index[tag][tid]["record"], "reason": "该 TP 无任何关联用例（覆盖缺口，需人工确认）"})

    # 数量守恒：逐 TP 直属 TC 数 M >= 2；M=0 由覆盖缺口 warning 承载，不判 failures
    if args.tp and args.tc:
        for tag in sorted(tp_index):
            for tid in sorted(tp_index[tag]):
                entry = tp_index[tag][tid]
                if 0 < entry["tc_count"] < 2:
                    failures.append(
                        {
                            "record": entry["record"],
                            "field": "用例数量",
                            "anchor": "M={}".format(entry["tc_count"]),
                            "reason": "直属用例仅 {} 条，少于下限 2 条——按 test-case-workflow「展开数量守恒」补齐，禁空壳充数".format(entry["tc_count"]),
                        }
                    )

    summary["failures"] = len(failures)
    summary["warnings"] = len(warnings)
    payload = {"ok": not failures, "summary": summary, "failures": failures, "warnings": warnings, "entry_lines": entry_lines}

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    # --out 仅兼容既有命令；结果只打印，不落盘
    # if args.out:
    #     with open(args.out, "w", encoding="utf-8") as fh:
    #         fh.write(text + "\n")
    print(text)
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
