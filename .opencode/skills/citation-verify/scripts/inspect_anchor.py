#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib_citation import (
    DOCX_POS,
    MD_POS,
    XLSX_POS,
    core_quote,
    docx_paragraphs,
    find_candidates,
    is_heading,
    norm,
    read_lines,
    split_anchor,
    xlsx_cell,
)


def trim(text, limit=400):
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "..."


def show_md(pos, mx, roots):
    fname = mx.group("file")
    start, end = int(mx.group("start")), int(mx.group("end") or mx.group("start"))
    cands = find_candidates(fname, roots)
    if not cands:
        print("  ✗ 未找到原文文件：{}".format(fname))
        return
    for path in cands:
        lines = read_lines(path)
        print("  原文：{}（共{}行）".format(path, len(lines)))
        if start < 1 or end < start or end > len(lines):
            print("  ✗ 行区间 {}-{} 越界".format(start, end))
            continue
        print("  第{}-{}行内容：{}".format(start, end, trim(" ".join(lines[start - 1 : end]))))


def show_docx(pos, mx, roots):
    fname, section = mx.group("file"), mx.group("section")
    cands = find_candidates(fname, roots)
    if not cands:
        print("  ✗ 未找到原文文件：{}".format(fname))
        return
    for path in cands:
        paras = docx_paragraphs(path)
        heads = [(i, t) for i, (st, t) in enumerate(paras) if is_heading(st)]
        if not heads:
            print("  ✗ {} 无章节结构（无Heading样式）→ 应升级澄清".format(path))
            continue
        sec_n = norm(section)
        hit = None
        for i, t in heads:
            t_n = norm(t)
            if sec_n == t_n or sec_n in t_n or t_n in sec_n:
                hit = i
                break
        if hit is None:
            print("  ✗ {} 未找到章节「{}」".format(path, section))
            print("  现有章节：{}".format(" / ".join(trim(t, 40) for _i, t in heads)))
            continue
        nxt = len(paras)
        for j, _t in heads:
            if j > hit:
                nxt = j
                break
        body = " ".join(paras[k][1] for k in range(hit, nxt))
        print("  原文：{} §{}".format(path, paras[hit][1]))
        print("  章节内容：{}".format(trim(body)))


def show_xlsx(pos, mx, roots):
    fname, sheet, cell = mx.group("file"), mx.group("sheet"), mx.group("cell")
    cands = find_candidates(fname, roots)
    if not cands:
        print("  ✗ 未找到原文文件：{}".format(fname))
        return
    for path in cands:
        value, err = xlsx_cell(path, sheet, cell)
        if err:
            print("  ✗ {}：{}".format(path, err))
            continue
        print("  原文：{} 表[{}] 单元格[{}]".format(path, sheet, cell))
        print("  单元格内容：{}".format(trim(value)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="append", required=True, help="原文检索根目录，可重复")
    ap.add_argument("--anchor", action="append", required=True, help="要检视的锚点，可重复")
    args = ap.parse_args()

    for raw in args.anchor:
        print("锚点：{}".format(raw))
        parsed = split_anchor(raw)
        if parsed is None:
            print("  ✗ 锚点格式非法（应为 位置 => \"摘抄\"）")
            continue
        pos, quote = parsed
        core, truncated = core_quote(quote)
        mx = XLSX_POS.match(pos)
        if mx:
            show_xlsx(pos, mx, args.docs)
        elif DOCX_POS.match(pos):
            show_docx(pos, DOCX_POS.match(pos), args.docs)
        elif MD_POS.match(pos):
            show_md(pos, MD_POS.match(pos), args.docs)
        else:
            print("  ✗ 锚点位置格式不识别：{}".format(pos))
            continue
        print("  摘抄（{}字{}）：{}".format(len(core), "，截断" if truncated else "", quote))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
