import os
import re
import zipfile
import xml.etree.ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
P_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

XLSX_POS = re.compile(r"^(?P<file>.+?\.xlsx)#(?P<sheet>.+?)!(?P<cell>[A-Za-z]{1,3}\d+)$", re.IGNORECASE)
DOCX_POS = re.compile(r"^(?P<file>.+?\.docx)#(?P<section>.+)$", re.IGNORECASE)
MD_POS = re.compile(r"^(?P<file>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")
CLAR_REF = re.compile(r"^(C-\d+)(\(默认\))?$")
SEP_LINE = re.compile(r"^:?-{3,}:?$")
MAX_QUOTE = 50


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def split_anchor(anchor):
    a = anchor.strip()
    if "=>" not in a:
        return None
    pos, quote = a.rsplit("=>", 1)
    pos = pos.strip()
    quote = quote.strip()
    if len(quote) < 2 or not (quote.startswith('"') and quote.endswith('"')):
        return None
    return pos, quote[1:-1]


def core_quote(q):
    q = q.strip()
    truncated = False
    while q and q[-1] in ".…":
        truncated = True
        q = q[:-1]
    return q, truncated


def anchors_of(cell):
    if not cell:
        return []
    return [a.strip() for a in cell.split(";;") if a.strip()]


def find_candidates(basename, roots):
    exact = []
    loose = []
    want = basename.strip()
    want_low = want.lower()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if fn == want:
                    exact.append(os.path.join(dirpath, fn))
                elif fn.lower() == want_low:
                    loose.append(os.path.join(dirpath, fn))
    return exact or loose


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def docx_paragraphs(path):
    with zipfile.ZipFile(path) as zh:
        data = zh.read("word/document.xml")
    root = ET.fromstring(data)
    paras = []
    for p in root.iter(W_NS + "p"):
        text = "".join(t.text or "" for t in p.iter(W_NS + "t"))
        style = ""
        ppr = p.find(W_NS + "pPr")
        if ppr is not None:
            pstyle = ppr.find(W_NS + "pStyle")
            if pstyle is not None:
                style = pstyle.get(W_NS + "val") or ""
        paras.append((style, text))
    return paras


def is_heading(style):
    s = (style or "").lower()
    return bool(s) and ("heading" in s or "标题" in s)


def xlsx_shared(zh):
    shared = []
    if "xl/sharedStrings.xml" in zh.namelist():
        root = ET.fromstring(zh.read("xl/sharedStrings.xml"))
        for si in root:
            shared.append("".join(t.text or "" for t in si.iter(M_NS + "t")))
    return shared


def xlsx_cell(path, sheet, coord):
    with zipfile.ZipFile(path) as zh:
        if "xl/workbook.xml" not in zh.namelist():
            return None, "损坏的xlsx：缺少workbook.xml"
        wb = ET.fromstring(zh.read("xl/workbook.xml"))
        rid = None
        for sh in wb.iter(M_NS + "sheet"):
            if norm(sh.get("name") or "") == norm(sheet):
                rid = sh.get(R_ATTR)
                break
        if rid is None:
            return None, "未找到Sheet：{}".format(sheet)
        rels_path = "xl/_rels/workbook.xml.rels"
        if rels_path not in zh.namelist():
            return None, "损坏的xlsx：缺少rels"
        rels = ET.fromstring(zh.read(rels_path))
        target = None
        for rel in rels.iter(P_NS + "Relationship"):
            if rel.get("Id") == rid:
                target = rel.get("Target") or ""
                break
        if not target:
            return None, "未找到Sheet对应的工作表：{}".format(sheet)
        inner = target.lstrip("/")
        if not inner.startswith("xl/"):
            inner = "xl/" + inner
        if inner not in zh.namelist():
            return None, "损坏的xlsx：缺少{} ".format(inner)
        shared = xlsx_shared(zh)
        ws = ET.fromstring(zh.read(inner))
        for c in ws.iter(M_NS + "c"):
            if (c.get("r") or "").upper() != coord.upper():
                continue
            ctype = c.get("t") or ""
            v = c.find(M_NS + "v")
            if ctype == "s" and v is not None:
                idx = int(v.text)
                if 0 <= idx < len(shared):
                    return shared[idx], None
                return None, "共享串索引越界"
            if ctype == "inlineStr":
                is_el = c.find(M_NS + "is")
                if is_el is not None:
                    return "".join(t.text or "" for t in is_el.iter(M_NS + "t")), None
            if v is not None and v.text is not None:
                return v.text, None
            return "", None
        return None, "未找到单元格：{}".format(coord)


def check_quote_common(quote):
    if not quote.strip():
        return "摘抄为空"
    core, _truncated = core_quote(quote)
    if not core:
        return "摘抄为空"
    if len(core) > MAX_QUOTE:
        return "摘抄超过50字（{}字）".format(len(core))
    return None


def check_anchor(anchor, roots):
    parsed = split_anchor(anchor)
    if parsed is None:
        return "锚点格式非法（应为 位置 => \"摘抄\"）"
    pos, quote = parsed
    err = check_quote_common(quote)
    if err:
        return err
    core, truncated = core_quote(quote)
    core_n = norm(core)

    mx = XLSX_POS.match(pos)
    if mx:
        cands = find_candidates(mx.group("file"), roots)
        if not cands:
            return "未找到原文文件：{}".format(mx.group("file"))
        reasons = []
        for path in cands:
            try:
                value, err = xlsx_cell(path, mx.group("sheet"), mx.group("cell"))
            except Exception as exc:
                reasons.append("{}: 解析失败 {}".format(path, exc))
                continue
            if err:
                reasons.append("{}: {}".format(path, err))
                continue
            if core_n and core_n in norm(value):
                return None
            reasons.append("{}: 单元格内容未匹配到摘抄".format(path))
        return "；".join(reasons)

    md_ = DOCX_POS.match(pos)
    if md_:
        section = md_.group("section")
        cands = find_candidates(md_.group("file"), roots)
        if not cands:
            return "未找到原文文件：{}".format(md_.group("file"))
        reasons = []
        for path in cands:
            try:
                paras = docx_paragraphs(path)
            except Exception as exc:
                reasons.append("{}: 解析失败 {}".format(path, exc))
                continue
            heads = [(i, t) for i, (st, t) in enumerate(paras) if is_heading(st)]
            if not heads:
                reasons.append("{}: 无章节结构（无Heading样式）→ 应升级澄清".format(path))
                continue
            sec_n = norm(section)
            hit = None
            for i, t in heads:
                t_n = norm(t)
                if sec_n == t_n or sec_n in t_n or t_n in sec_n:
                    hit = i
                    break
            if hit is None:
                reasons.append("{}: 未找到章节「{}」".format(path, section))
                continue
            nxt = len(paras)
            for j, _t in heads:
                if j > hit:
                    nxt = j
                    break
            body = " ".join(paras[k][1] for k in range(hit, nxt))
            if core_n and core_n in norm(body):
                return None
            reasons.append("{}: 章节「{}」内未匹配到摘抄".format(path, section))
        return "；".join(reasons)

    m = MD_POS.match(pos)
    if m:
        fname = m.group("file")
        start = int(m.group("start"))
        end = int(m.group("end") or start)
        cands = find_candidates(fname, roots)
        if not cands:
            return "未找到原文文件：{}".format(fname)
        if start < 1 or end < start:
            return "行区间非法：{}".format(pos)
        reasons = []
        for path in cands:
            lines = read_lines(path)
            if end > len(lines):
                reasons.append("{}: 行{}越界（共{}行）".format(path, end, len(lines)))
                continue
            piece = " ".join(lines[start - 1 : end])
            if core_n and core_n in norm(piece):
                return None
            reasons.append("{}: 行{}-{}内未匹配到摘抄".format(path, start, end))
        return "；".join(reasons)

    return "锚点位置格式不识别：{}".format(pos)


def parse_md_tables(text):
    tables = []
    block = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            block.append(s)
        else:
            if block:
                tables.append(block)
                block = []
    if block:
        tables.append(block)
    parsed = []
    for rows_raw in tables:
        header = None
        body = []
        for s in rows_raw:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(SEP_LINE.match(c or "---") for c in cells):
                continue
            if header is None:
                header = cells
                continue
            if len(cells) < len(header):
                cells = cells + [""] * (len(header) - len(cells))
            rec = dict(zip(header, [c.strip() for c in cells]))
            body.append(rec)
        body = [r for r in body if any(v for v in r.values())]
        if header:
            parsed.append((header, body))
    return parsed


def table_with_columns(text, required):
    for header, rows in parse_md_tables(text):
        if all(col in header for col in required):
            return header, rows
    return None, None


def table_fragment_count(text):
    """返回文件解析出的表格片段数（含孤儿片段）。契约清单文件应为单表；>1 时首表之外的数据行不可见。"""
    return len(parse_md_tables(text))


def broken_table_rows(text):
    """检测疑似被真实换行打断的表格行：以 | 开头但未以 | 结尾。
    单元格内换行应使用 <br> 字面量；真实换行会使 parse_md_tables 静默跳过该行。"""
    warns = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("|") and len(s) > 1 and not s.endswith("|"):
            warns.append((i, s[:40]))
    return warns
