#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys

from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib_citation import (
    CLAR_REF,
    anchors_of,
    broken_table_rows,
    check_anchor,
    table_fragment_count,
    table_with_columns,
)

TP_REQUIRED = ["编号", "关联业务功能", "测试点名称", "类型", "测试维度", "所属小类", "用例展开重点", "澄清依据", "出处锚点"]
TC_REQUIRED = ["编号", "关联业务功能", "关联TP", "用例名称", "用例类型", "测试方法", "前置条件", "测试数据", "操作步骤", "预期结果", "澄清依据", "出处锚点"]
CLAR_REQUIRED = ["编号", "来源", "问题", "影响面", "默认建议", "答复", "状态"]
OUT_NAME = re.compile(r"^citation-result.*\.json$")

# 测试维度 → 《测试维度定义》§二合法小类集（单值；维度-小类组合合法性机验依据）
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
# 测试方法六枚举（《通用测试方法论》§七方法选型，单值白名单）
TC_METHODS = {"等价类+边界值", "决策表", "状态迁移", "场景法", "正交实验", "错误推测"}

# 用例展开重点：多值分隔符与元描述剔除（项数 N 是 TC 数量下限的唯一定量来源）
FOCUS_SEP = ";;"
FOCUS_META = re.compile(r"每项至少|至少\s*\d+\s*条|条用例|覆盖正向|正向反向|正反向")


def count_focus_items(text):
    """统计 `用例展开重点` 的实项数：按 ;; 拆分，剔除元描述项（通则不是展开点）。"""
    items = [s.strip() for s in (text or "").split(FOCUS_SEP)]
    return len([s for s in items if s and not FOCUS_META.search(s)])


def load_rows(path, required, kind):
    if not path:
        return None, None, []
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
    frag = table_fragment_count(text)
    if frag > 1:
        warns.append(
            {
                "record": kind + " 表格结构",
                "reason": "文件解析出 {} 个表格片段——首表之外的数据行已静默跳过（疑似断行后的孤立片段，应修复断行并整表重排）".format(frag),
            }
        )
    return header, rows, warns


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


def check_clar_ref(value, clar_set, record, failures, has_clar):
    v = (value or "").strip()
    if v in ("-", ""):
        return
    # 多值：用 ` ;; ` 分隔（与锚点列同风格），逐个校验格式与存在性
    for seg in [p.strip() for p in v.split(";;") if p.strip()]:
        if not CLAR_REF.match(seg):
            failures.append({"record": record, "field": "澄清依据", "anchor": seg, "reason": "澄清依据格式非法（应为 C-编号 或 C-编号(默认)，多值用 ;; 分隔）"})
            continue
        cid = CLAR_REF.match(seg).group(1)
        if has_clar and cid not in clar_set:
            failures.append({"record": record, "field": "澄清依据", "anchor": seg, "reason": "澄清编号 {} 在 clarifications.md 中不存在".format(cid)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="append", required=True, help="原文检索根目录，可重复")
    ap.add_argument("--tp", help="tp/test-point-table.md 路径")
    ap.add_argument("--tc", help="tc/test-case-table.md 路径")
    ap.add_argument("--clar", help="state/clarifications.md 路径")
    ap.add_argument("--out", help="结果 JSON 输出路径（文件名须为 citation-result*.json）")
    args = ap.parse_args()

    if args.out and not OUT_NAME.match(os.path.basename(args.out)):
        fatal(["--out 文件名必须匹配 citation-result*.json，收到：{}".format(os.path.basename(args.out))])

    if not args.tp and not args.tc:
        fatal(["至少提供 --tp 或 --tc 之一"])

    docs = [d for d in (args.docs or [])]
    if not docs:
        fatal(["至少需要一个 --docs 目录"])

    failures = []
    warnings = []
    summary = {"tp_rows": 0, "tc_rows": 0, "checks": 0, "failures": 0, "warnings": 0}

    tp_ids = set()
    tp_names = {}
    tp_funcs = {}
    tp_focus_n = {}
    tp_tc_count = {}
    covered = set()

    clar_set = set()
    has_clar = False
    if args.clar:
        _h, crows, w = load_rows(args.clar, CLAR_REQUIRED, "clarifications")
        warnings.extend(w)
        if crows is not None:
            has_clar = True
            for r in crows:
                cid = (r.get("编号") or "").strip()
                if cid:
                    clar_set.add(cid)

    if args.tp:
        _h, tp_rows, w = load_rows(args.tp, TP_REQUIRED, "TP清单")
        warnings.extend(w)
        summary["tp_rows"] = len(tp_rows)
        for r in tp_rows:
            tid = (r.get("编号") or "").strip()
            if not re.fullmatch(r"TP-\d+", tid):
                failures.append({"record": tid or "(空)", "field": "编号", "anchor": "-", "reason": "TP 编号格式非法（应为 TP-数字）"})
                continue
            tp_ids.add(tid)
            tp_names[tid] = (r.get("测试点名称") or "").strip()
            tp_funcs[tid] = (r.get("关联业务功能") or "").strip()
            anc = anchors_of(r.get("出处锚点"))
            if not anc:
                failures.append({"record": tid, "field": "出处锚点", "anchor": "-", "reason": "锚点为空（每个测试点必须有出处）"})
            for a in anc:
                summary["checks"] += 1
                reason = check_anchor(a, docs)
                if reason:
                    failures.append({"record": tid, "field": "出处锚点", "anchor": a, "reason": reason})
            check_clar_ref(r.get("澄清依据"), clar_set, tid, failures, has_clar)
            dim = (r.get("测试维度") or "").strip()
            sub = (r.get("所属小类") or "").strip()
            if dim not in TP_DIMENSIONS:
                failures.append({"record": tid, "field": "测试维度", "anchor": dim or "(空)", "reason": "测试维度非法（须为《测试维度定义》§一维度枚举，单值）"})
            elif not sub:
                failures.append({"record": tid, "field": "所属小类", "anchor": "(空)", "reason": "所属小类为空（须填写小类层，单值）"})
            elif sub not in TP_DIMENSIONS[dim]:
                failures.append({"record": tid, "field": "所属小类", "anchor": sub, "reason": "所属小类 {} 不属于测试维度 {} 的合法小类集".format(sub, dim)})
            tp_type = (r.get("类型") or "").strip()
            if tp_type not in TP_TYPES:
                failures.append({"record": tid, "field": "类型", "anchor": tp_type or "(空)", "reason": "类型非法（仅 功能级/场景级）"})
            focus = (r.get("用例展开重点") or "").strip()
            focus_n = count_focus_items(focus)
            tp_focus_n[tid] = focus_n
            if focus_n == 0:
                failures.append({"record": tid, "field": "用例展开重点", "anchor": "-", "reason": "用例展开重点为空（至少 2 个可独立判定的展开项）"})
            elif focus_n < 2:
                failures.append({"record": tid, "field": "用例展开重点", "anchor": focus, "reason": "用例展开重点仅 {} 个实项，少于 2 项；两项须为可独立判定的分支，且不得以\"每项至少 1 条用例\"类元描述充数".format(focus_n)})

    if args.tc:
        _h, tc_rows, w = load_rows(args.tc, TC_REQUIRED, "TC清单")
        warnings.extend(w)
        summary["tc_rows"] = len(tc_rows)
        for r in tc_rows:
            tcid = (r.get("编号") or "").strip()
            if not re.fullmatch(r"TC-\d+", tcid):
                failures.append({"record": tcid or "(空)", "field": "编号", "anchor": "-", "reason": "TC 编号格式非法（应为 TC-数字）"})
                continue
            ref_raw = (r.get("关联TP") or "").strip()
            ref, _, name_seg = ref_raw.partition(" ")
            ref = ref.strip()
            name_seg = name_seg.strip()
            if not re.fullmatch(r"TP-\d+", ref):
                failures.append({"record": tcid, "field": "关联TP", "anchor": ref_raw or "(空)", "reason": "关联TP 编号段格式非法（应为 TP-数字，第一个空格分隔编号与名称）"})
            elif ref not in tp_ids:
                failures.append({"record": tcid, "field": "关联TP", "anchor": ref, "reason": "关联TP {} 在 TP 清单中不存在".format(ref)})
            else:
                covered.add(ref)
                tp_tc_count[ref] = tp_tc_count.get(ref, 0) + 1
                if not name_seg:
                    failures.append({"record": tcid, "field": "关联TP", "anchor": ref_raw, "reason": "关联TP 缺名称段（应为 编号+名称 双信息，第一个空格分隔）"})
                elif tp_names.get(ref, "") != name_seg:
                    failures.append({"record": tcid, "field": "关联TP", "anchor": name_seg, "reason": "关联TP 名称段与 TP 清单中 {} 的测试点名称不一致".format(ref)})
                tp_func = (r.get("关联业务功能") or "").strip()
                if tp_funcs.get(ref) is not None and tp_func != tp_funcs.get(ref):
                    failures.append({"record": tcid, "field": "关联业务功能", "anchor": tp_func, "reason": "关联业务功能与主 TP {} 的关联业务功能不一致".format(ref)})
            m = (r.get("测试方法") or "").strip()
            if m not in TC_METHODS:
                failures.append({"record": tcid, "field": "测试方法", "anchor": m or "(空)", "reason": "测试方法非法（六枚举：等价类+边界值/决策表/状态迁移/场景法/正交实验/错误推测，单值）"})
            anc = anchors_of(r.get("出处锚点"))
            if not anc:
                failures.append({"record": tcid, "field": "出处锚点", "anchor": "-", "reason": "锚点为空（每个用例必须有出处）"})
            for a in anc:
                summary["checks"] += 1
                reason = check_anchor(a, docs)
                if reason:
                    failures.append({"record": tcid, "field": "出处锚点", "anchor": a, "reason": reason})
            check_clar_ref(r.get("澄清依据"), clar_set, tcid, failures, has_clar)

    for tid in sorted(tp_ids - covered):
        warnings.append({"record": tid, "reason": "该 TP 无任何关联用例（覆盖缺口，需人工确认）"})

    # 数量守恒：直属 TC 数 M 必须 ≥ 展开重点实项数 N（下限 2）；拦截"每 TP 正好 2 条"式均摊
    if args.tp and args.tc:
        for tid in sorted(tp_ids):
            n = tp_focus_n.get(tid, 0)
            m = tp_tc_count.get(tid, 0)
            floor = max(n, 2)
            if m and m < floor:
                failures.append(
                    {
                        "record": tid,
                        "field": "用例数量",
                        "anchor": "M={} / N={}".format(m, n),
                        "reason": "直属用例 {} 条，少于展开重点项数 {}（下限 {}）——按 test-case-workflow「展开数量守恒」逐项补齐，禁改小 N、禁均摊或空壳充数".format(m, n, floor),
                    }
                )
        counts = [tp_tc_count[t] for t in tp_ids if tp_tc_count.get(t, 0) > 0]
        if len(counts) >= 5:
            mode_val, mode_cnt = Counter(counts).most_common(1)[0]
            if mode_cnt / len(counts) > 0.5:
                warnings.append(
                    {
                        "record": "TC清单",
                        "reason": "过半 TP 的直属用例数均为 {}（{}/{} 个 TP），疑似按 TP 均摊条数凑数（典型：每个 TP 都正好 2 条）——逐 TP 按形态算法复核展开重点项数".format(mode_val, mode_cnt, len(counts)),
                    }
                )

    summary["failures"] = len(failures)
    summary["warnings"] = len(warnings)
    payload = {"ok": not failures, "summary": summary, "failures": failures, "warnings": warnings}

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
