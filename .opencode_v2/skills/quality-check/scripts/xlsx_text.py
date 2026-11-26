# -*- coding: utf-8 -*-
"""xlsx 单元格读取工具：按 Sheet+行号输出文本，供索引构建与原文回读。

锚点写法：文件名.xlsx:Sheet名#单元格 => "摘抄"（区间 B3:D5），行号即 Excel 物理行号。
Sheet 名与行号一律照抄本工具输出。
"""
import argparse
import sys
import zipfile
import xml.etree.ElementTree as ET

from lib_citation import M_NS, norm, xlsx_rows

CELL_MAX = 60  # 单元格输出截断
SEARCH_MAX = 50


def cmd_sheets(path):
    """列出 Sheet 名与行列规模。"""
    with zipfile.ZipFile(path) as zh:
        import xml.etree.ElementTree as _ET
        wb = _ET.fromstring(zh.read("xl/workbook.xml"))
        names = [sh.get("name") for sh in wb.iter(M_NS + "sheet")]
    for name in names:
        rows = xlsx_rows(path, name)
        max_row = rows[-1][0] if rows else 0
        cols = sorted({c for _r, cells in rows for c in cells})
        print("{}: {} 行非空, 列 {}".format(name, len(rows), ",".join(cols) if cols else "无"))


def cmd_rows(path, sheet, a, b):
    """输出 Sheet 第 a-b 行，每行一行文本。"""
    try:
        rows = xlsx_rows(path, sheet)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    idx = dict(rows)
    for rn in range(a, b + 1):
        if rn not in idx:
            continue
        parts = ["{}={}".format(c, norm(t)[:CELL_MAX]) for c, t in sorted(idx[rn].items())]
        print("R{}: {}".format(rn, " | ".join(parts)))
    return 0


def cmd_search(path, kw):
    """跨 Sheet 搜索关键词，输出定位坐标。"""
    hits = 0
    with zipfile.ZipFile(path) as zh:
        wb = ET.fromstring(zh.read("xl/workbook.xml"))
        names = [sh.get("name") for sh in wb.iter(M_NS + "sheet")]
    for name in names:
        try:
            rows = xlsx_rows(path, name)
        except ValueError:
            continue
        for rn, cells in rows:
            for col, text in sorted(cells.items()):
                if kw in text:
                    print("{}#{}{}: {}".format(name, col, rn, norm(text)[:80]))
                    hits += 1
                    if hits >= SEARCH_MAX:
                        print("……命中超过 {} 条".format(SEARCH_MAX))
                        return 0
    if hits == 0:
        print("未命中：{}".format(kw))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("xlsx", help="xlsx 绝对路径")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sheets", action="store_true", help="列出 Sheet 与规模")
    g.add_argument("--rows", nargs=3, metavar=("SHEET", "A", "B"), help="输出指定行区间")
    g.add_argument("--search", metavar="KW", help="跨 Sheet 搜索")
    args = ap.parse_args()

    try:
        if args.sheets:
            cmd_sheets(args.xlsx)
            sys.exit(0)
        if args.rows:
            sys.exit(cmd_rows(args.xlsx, args.rows[0], int(args.rows[1]), int(args.rows[2])))
        sys.exit(cmd_search(args.xlsx, args.search))
    except Exception as exc:
        print("解析失败：{}".format(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
