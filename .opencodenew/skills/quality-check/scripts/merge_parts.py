#!/usr/bin/env python3
"""汇总：扫描会话目录里的 JSON 分片并拼接为汇总视图，供关口展示。

用法：
  python3 merge_parts.py --session <会话目录绝对路径> --kind tp|tc

  --session  会话目录，脚本在其中定位分片并写入汇总文件
  --kind     tp：扫描 output/tp/parts/tp-B*.json，写入 output/tp/test-point-table.json
             tc：扫描 output/tc/parts/tc-B*.json，写入 output/tc/test-case-table.json

脚本自动按文件名批号升序拼接，调用方无需传入分片清单。机械拼接：不改条目、不重编号、不去重。各分片已独立质检，汇总视图不质检。
"""
import argparse
import glob
import json
import os
import re
import sys

BATCH_RE = re.compile(r"-B(\d+)\.json$")
# (子目录, 分片前缀, 汇总文件名, 顶层清单类型值, 条目数组键名)
KIND_LAYOUT = {
    "tp": ("tp", "tp", "test-point-table.json", "测试点清单", "测试点"),
    "tc": ("tc", "tc", "test-case-table.json", "测试用例清单", "测试用例"),
}


def batch_no(path):
    m = BATCH_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


def locate_parts(session, sub, prefix):
    pattern = os.path.join(session, "output", sub, "parts", prefix + "-B*.json")
    paths = [p for p in glob.glob(pattern) if batch_no(p) is not None]
    if not paths:
        sys.exit("未找到分片：{}".format(pattern))
    return sorted(paths, key=batch_no)


def merge_items(paths, list_key):
    """按批号顺序拼接各分片的条目数组；分片结构非法即致命退出。"""
    items = []
    for path in paths:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            try:
                data = json.load(fh)
            except ValueError as exc:
                sys.exit("分片 JSON 解析失败：{}（{}）".format(path, exc))
        rows = data.get(list_key) if isinstance(data, dict) else None
        if not isinstance(rows, list):
            sys.exit("分片缺少 `{}` 数组：{}".format(list_key, path))
        items.extend(rows)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, help="会话目录绝对路径")
    ap.add_argument("--kind", required=True, choices=["tp", "tc"])
    args = ap.parse_args()

    sub, prefix, out_name, list_type, list_key = KIND_LAYOUT[args.kind]
    paths = locate_parts(args.session, sub, prefix)
    items = merge_items(paths, list_key)
    text = json.dumps({"清单类型": list_type, list_key: items}, ensure_ascii=False, indent=2)

    out_path = os.path.join(args.session, "output", sub, out_name)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")

    print("汇总完成：{}（{} 个分片，{} 条，kind={}）".format(out_path, len(paths), len(items), args.kind))


if __name__ == "__main__":
    main()
