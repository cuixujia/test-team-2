#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib_citation import (
    CLAR_REF,
    anchors_of,
    check_anchor,
    table_with_columns,
)

TP_REQUIRED = ["编号", "关联业务功能", "测试点名称", "类型", "澄清依据", "出处锚点"]
TC_REQUIRED = ["编号", "关联业务功能", "关联TP", "用例名称", "用例类型", "前置条件", "测试数据", "操作步骤", "预期结果", "澄清依据", "出处锚点"]
CLAR_REQUIRED = ["编号", "来源", "问题", "影响面", "默认建议", "答复", "状态"]
OUT_NAME = re.compile(r"^citation-result.*\.json$")


def load_rows(path, required, kind):
    if not path:
        return None, None
    if not os.path.isfile(path):
        fatal(["{} 文件不存在：{}".format(kind, path)])
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.strip():
        fatal(["{} 文件为空：{}".format(kind, path)])
    header, rows = table_with_columns(text, required)
    if header is None:
        fatal(["{} 表头缺少必需列，需要：{}".format(kind, "、".join(required))])
    return header, rows


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
    if not CLAR_REF.match(v):
        failures.append({"record": record, "field": "澄清依据", "anchor": v, "reason": "澄清依据格式非法（应为 C-编号 或 C-编号(默认) 或 -）"})
        return
    cid = CLAR_REF.match(v).group(1)
    if has_clar and cid not in clar_set:
        failures.append({"record": record, "field": "澄清依据", "anchor": v, "reason": "澄清编号 {} 在 clarifications.md 中不存在".format(cid)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="append", required=True, help="原文检索根目录，可重复")
    ap.add_argument("--tp", help="tp/list.md 路径")
    ap.add_argument("--tc", help="tc/list.md 路径")
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
    covered = set()

    clar_set = set()
    has_clar = False
    if args.clar:
        _h, crows = load_rows(args.clar, CLAR_REQUIRED, "clarifications")
        if crows is not None:
            has_clar = True
            for r in crows:
                cid = (r.get("编号") or "").strip()
                if cid:
                    clar_set.add(cid)

    if args.tp:
        _h, tp_rows = load_rows(args.tp, TP_REQUIRED, "TP清单")
        summary["tp_rows"] = len(tp_rows)
        for r in tp_rows:
            tid = (r.get("编号") or "").strip()
            if not re.fullmatch(r"TP-\d+", tid):
                failures.append({"record": tid or "(空)", "field": "编号", "anchor": "-", "reason": "TP 编号格式非法（应为 TP-数字）"})
                continue
            tp_ids.add(tid)
            anc = anchors_of(r.get("出处锚点"))
            if not anc:
                failures.append({"record": tid, "field": "出处锚点", "anchor": "-", "reason": "锚点为空（每个测试点必须有出处）"})
            for a in anc:
                summary["checks"] += 1
                reason = check_anchor(a, docs)
                if reason:
                    failures.append({"record": tid, "field": "出处锚点", "anchor": a, "reason": reason})
            check_clar_ref(r.get("澄清依据"), clar_set, tid, failures, has_clar)

    if args.tc:
        _h, tc_rows = load_rows(args.tc, TC_REQUIRED, "TC清单")
        summary["tc_rows"] = len(tc_rows)
        for r in tc_rows:
            tcid = (r.get("编号") or "").strip()
            if not re.fullmatch(r"TC-\d+", tcid):
                failures.append({"record": tcid or "(空)", "field": "编号", "anchor": "-", "reason": "TC 编号格式非法（应为 TC-数字）"})
                continue
            ref = (r.get("关联TP") or "").strip()
            if ref not in tp_ids:
                failures.append({"record": tcid, "field": "关联TP", "anchor": ref, "reason": "关联TP {} 在 TP 清单中不存在".format(ref)})
            else:
                covered.add(ref)
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
