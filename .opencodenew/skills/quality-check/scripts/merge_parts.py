#!/usr/bin/env python3
"""汇总：扫描会话目录里的分片并拼接为汇总视图，供关口展示。

用法：
  python3 merge_parts.py --session <会话目录绝对路径> --kind tp|tc

  --session  会话目录，脚本在其中定位分片并写入汇总文件
  --kind     tp：扫描 output/tp/parts/tp-B*.md，写入 output/tp/test-point-table.md
             tc：扫描 output/tc/parts/tc-B*.md，写入 output/tc/test-case-table.md

脚本自动按文件名批号升序拼接，调用方无需传入分片清单。机械拼接：不改条目、不重编号、不去重。各分片已独立质检，汇总视图不质检。
"""
import argparse
import glob
import os
import re
import sys

BATCH_RE = re.compile(r"-B(\d+)\.md$")
KIND_LAYOUT = {
    "tp": ("tp", "tp", "test-point-table.md"),
    "tc": ("tc", "tc", "test-case-table.md"),
}


def batch_no(path):
    m = BATCH_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


def locate_parts(session, sub, prefix):
    pattern = os.path.join(session, "output", sub, "parts", prefix + "-B*.md")
    paths = [p for p in glob.glob(pattern) if batch_no(p) is not None]
    if not paths:
        sys.exit("未找到分片：{}".format(pattern))
    return sorted(paths, key=batch_no)


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read().rstrip("\n")


def split_table(text):
    """分离标题/引言区与表格区；表格区从首个表头行起。"""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|") and "编号" in line:
            return "\n".join(lines[:i]).rstrip("\n"), lines[i:]
    return text.rstrip("\n"), []


def is_data_line(line):
    return bool(re.match(r"^\|\s*(TP|TC)-\d+", line.strip()))


def merge_table(paths):
    """首个分片取标题与表头，各分片只取编号数据行，按批号顺序拼接。"""
    head_part = ""
    header = []
    data_lines = []
    for path in paths:
        head, rows = split_table(read(path))
        if not rows:
            continue
        if not header:
            head_part = head
            header = [r.rstrip() for r in rows[:2] if r.strip().startswith("|")]
        data_lines.extend(r.rstrip() for r in rows if is_data_line(r))
    head = head_part if head_part else "# 汇总"
    return head + "\n" + "\n".join(header + data_lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, help="会话目录绝对路径")
    ap.add_argument("--kind", required=True, choices=["tp", "tc"])
    args = ap.parse_args()

    sub, prefix, out_name = KIND_LAYOUT[args.kind]
    paths = locate_parts(args.session, sub, prefix)
    text = merge_table(paths)

    out_path = os.path.join(args.session, "output", sub, out_name)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("汇总完成：{}（{} 个分片，kind={}）".format(out_path, len(paths), args.kind))


if __name__ == "__main__":
    main()
