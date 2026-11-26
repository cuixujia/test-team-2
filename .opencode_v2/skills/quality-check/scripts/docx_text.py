# -*- coding: utf-8 -*-
"""docx 段落读取工具：按段落号输出纯文本，供索引构建与原文回读。

段落号口径与机验一致：仅计非空段落、文档顺序编号（含表格内段落）、P1 起。
锚点写法：文件名.docx:P{N}#{所在节标题} => "摘抄"，P 号与标题一律照抄本工具输出。
"""
import argparse
import sys

from lib_citation import docx_paras, docx_section_title, is_heading, norm

TRUNC = 200  # 单段输出上限，超长段落截断
SEARCH_MAX = 50  # --search 最多命中条数


def heading_level(style):
    """Heading 样式转层级数字，非标题返回 0。"""
    digits = "".join(ch for ch in style if ch.isdigit())
    return int(digits) if digits else 1


def cmd_toc(paras):
    """输出标题树与各节段落区间：区间为该标题段到下一标题段之前。"""
    heads = [i for i, (st, _t) in enumerate(paras) if is_heading(st)]
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(paras) - 1
        st, text = paras[i]
        indent = "  " * (heading_level(st) - 1)
        print("{}P{}-P{} {}".format(indent, i + 1, end + 1, norm(text)))
    print("共 {} 个非空段落".format(len(paras)))


def pnum(s):
    """段落号入参：兼容 61 与 P61 两种写法。"""
    return int(str(s).lstrip("Pp"))


def parse_segs(args):
    """解析 --range 入参：支持 614 616 单区间与 614-616,900-935 多区间。"""
    if len(args) == 2 and not any(c in "".join(args) for c in "-,"):
        return [(pnum(args[0]), pnum(args[1]))]
    segs = []
    for a in args:
        for part in a.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                x, y = part.split("-", 1)
                segs.append((pnum(x), pnum(y)))
            else:
                n = pnum(part)
                segs.append((n, n))
    return segs


def cmd_range(paras, segs):
    """逐区间输出段落文本；越界自动钳位，节标题变化时输出分组行。"""
    n = len(paras)
    last_title = None
    for a, b in segs:
        a = max(1, min(a, n))
        b = max(a, min(b, n))
        for i in range(a - 1, b):
            title = norm(docx_section_title(paras, i))
            if title != last_title:
                print("## {}".format(title or "封面区"))
                last_title = title
            text = norm(paras[i][1])
            if len(text) > TRUNC:
                text = text[:TRUNC] + "…"
            print("P{} {}".format(i + 1, text))
    return 0


def cmd_search(paras, kw):
    """输出含关键词的段落及其锚点要素。"""
    hits = 0
    for i, (_st, text) in enumerate(paras):
        if kw in text:
            t = norm(text)
            pos = t.find(kw)
            lo = max(0, pos - 40)
            snippet = ("…" if lo else "") + t[lo:pos + len(kw) + 40] + ("…" if pos + len(kw) + 40 < len(t) else "")
            print("P{} #{} {}".format(i + 1, docx_section_title(paras, i), snippet))
            hits += 1
            if hits >= SEARCH_MAX:
                print("……命中超过 {} 条，请用更精确的关键词".format(SEARCH_MAX))
                break
    if hits == 0:
        print("未命中：{}".format(kw))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("docx", help="docx 绝对路径")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--toc", action="store_true", help="标题树与段落区间")
    g.add_argument("--all", action="store_true", help="输出全文所有段落")
    g.add_argument("--range", nargs="+", metavar="SEG", help="读段落：--range 614-616,900-935 或 --range 614 616")
    g.add_argument("--search", metavar="KW", help="按关键词定位段落")
    args = ap.parse_args()

    try:
        paras = docx_paras(args.docx)
    except Exception as exc:
        print("解析失败：{}".format(exc), file=sys.stderr)
        sys.exit(2)
    if not paras:
        print("文档无非空段落", file=sys.stderr)
        sys.exit(2)

    if args.toc:
        sys.exit(cmd_toc(paras) or 0)
    if args.all:
        sys.exit(cmd_range(paras, [(1, len(paras))]))
    if args.range:
        sys.exit(cmd_range(paras, parse_segs(args.range)))
    sys.exit(cmd_search(paras, args.search))


if __name__ == "__main__":
    main()
