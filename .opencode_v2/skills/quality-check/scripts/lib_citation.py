import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
P_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

XLSX_POS = re.compile(
    r"^(?P<file>.+?\.xlsx):(?P<sheet>[^#]+)#(?P<cell>[A-Za-z]{1,3}\d+)(?::(?P<cell2>[A-Za-z]{1,3}\d+))?$",
    re.IGNORECASE,
)
DOCX_POS = re.compile(
    r"^(?P<file>.+?\.docx):[Pp](?P<num>\d+)(?:#(?P<section>.+))?$",
    re.IGNORECASE,
)
MD_POS = re.compile(r"^(?P<file>.+?\.(?:md|txt|csv)):(?P<start>\d+)(?:-(?P<end>\d+))?$", re.IGNORECASE)
SEP_LINE = re.compile(r"^:?-{3,}:?$")


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
    return q.strip().rstrip(".…")


def as_list(value):
    """多值字段归一化为列表：JSON 数组逐项取字符串；markdown 字符串按 ` ;; ` 拆分。`-` 与空值视为无。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip() not in ("", "-")]
    return [p.strip() for p in str(value).split(";;") if p.strip() and p.strip() != "-"]


def anchors_of(cell):
    return as_list(cell)


def json_table_with_lines(path):
    """读取表格化 JSON 清单（顶层对象含 name、headers、rows），返回 (name, headers, rows, 条目行号列表, 错误信息)。
    rows 每条一行数组，单元格为字符串或字符串数组；一条数据占一个物理行，
    条目行号即该行行号，供语义验与复检按行精准读取单条。结构非法返回错误。"""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    if not text.strip():
        return None, None, None, None, "文件为空"
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, None, None, None, "JSON 解析失败：{}".format(exc)
    if not isinstance(data, dict):
        return None, None, None, None, "顶层须为对象（含 name、headers、rows）"
    name = data.get("name")
    headers = data.get("headers")
    rows = data.get("rows")
    if not isinstance(name, str) or not name.strip():
        return None, None, None, None, "缺少字符串字段 `name`"
    if not isinstance(headers, list) or not all(isinstance(h, str) and h.strip() for h in headers):
        return None, None, None, None, "`headers` 须为非空字符串数组"
    if not isinstance(rows, list):
        return None, None, None, None, "缺少 `rows` 数组"
    for i, r in enumerate(rows, 1):
        if not isinstance(r, list):
            return None, None, None, None, "`rows` 第 {} 条不是数组".format(i)
        if len(r) != len(headers):
            return None, None, None, None, "`rows` 第 {} 条长度 {} 与 headers 长度 {} 不一致".format(i, len(r), len(headers))
    # 定位 rows 开括号行：其后每个数据行即一条条目；空行跳过，遇闭合括号停止，避免行号错位
    marks = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(r'"rows"\s*:\s*\[', line):
            for j in range(i + 1, len(lines)):
                s = lines[j].strip()
                if not s:
                    continue
                if s.startswith("]"):
                    break
                marks.append(j + 1)
            break
    return name, headers, rows, marks, None


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


def docx_paras(path):
    """docx 非空段落枚举：跳过纯空白段落，按文档顺序编号 P1 起，含表格内段落。返回 [(style, text)]。
    编号口径与 docx_text.py 及机验分支完全一致，三处共用此函数。"""
    with zipfile.ZipFile(path) as zh:
        data = zh.read("word/document.xml")
    root = ET.fromstring(data)
    paras = []
    for p in root.iter(W_NS + "p"):
        text = "".join(t.text or "" for t in p.iter(W_NS + "t"))
        if not text.strip():
            continue
        style = ""
        ppr = p.find(W_NS + "pPr")
        if ppr is not None:
            pstyle = ppr.find(W_NS + "pStyle")
            if pstyle is not None:
                style = pstyle.get(W_NS + "val") or ""
        paras.append((style, text))
    return paras


def docx_section_title(paras, idx):
    """段落所在节标题：该段自身是 Heading 则取自身，否则取向上最近 Heading；无任何 Heading 则返回空串。"""
    for k in range(idx, -1, -1):
        if is_heading(paras[k][0]):
            return norm(paras[k][1])
    return ""


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


def col_num(s):
    """列字母转 1-based 列号：A=1, Z=26, AA=27。"""
    n = 0
    for ch in s.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def xlsx_rows(path, sheet):
    """解析指定 Sheet，返回 [(行号, {列字母: 文本})]，跳过空行。Sheet 不存在或文件损坏抛 ValueError。"""
    with zipfile.ZipFile(path) as zh:
        if "xl/workbook.xml" not in zh.namelist():
            raise ValueError("损坏的xlsx：缺少workbook.xml")
        wb = ET.fromstring(zh.read("xl/workbook.xml"))
        rid = None
        for sh in wb.iter(M_NS + "sheet"):
            if norm(sh.get("name") or "") == norm(sheet):
                rid = sh.get(R_ATTR)
                break
        if rid is None:
            raise ValueError("未找到Sheet：{}".format(sheet))
        rels_path = "xl/_rels/workbook.xml.rels"
        if rels_path not in zh.namelist():
            raise ValueError("损坏的xlsx：缺少rels")
        rels = ET.fromstring(zh.read(rels_path))
        target = None
        for rel in rels.iter(P_NS + "Relationship"):
            if rel.get("Id") == rid:
                target = rel.get("Target") or ""
                break
        if not target:
            raise ValueError("未找到Sheet对应的工作表：{}".format(sheet))
        inner = target.lstrip("/")
        if not inner.startswith("xl/"):
            inner = "xl/" + inner
        if inner not in zh.namelist():
            raise ValueError("损坏的xlsx：缺少{}".format(inner))
        shared = xlsx_shared(zh)
        ws = ET.fromstring(zh.read(inner))
        rows = []
        for row in ws.iter(M_NS + "row"):
            rn = int(row.get("r") or 0)
            cells = {}
            for c in row.iter(M_NS + "c"):
                ref = c.get("r") or ""
                m = re.match(r"([A-Za-z]+)(\d+)", ref)
                if not m:
                    continue
                col = m.group(1).upper()
                ctype = c.get("t") or ""
                v = c.find(M_NS + "v")
                text = ""
                if ctype == "s" and v is not None:
                    idx = int(v.text)
                    if 0 <= idx < len(shared):
                        text = shared[idx]
                elif ctype == "inlineStr":
                    is_el = c.find(M_NS + "is")
                    if is_el is not None:
                        text = "".join(t.text or "" for t in is_el.iter(M_NS + "t"))
                elif v is not None and v.text is not None:
                    text = v.text
                if text.strip():
                    cells[col] = text
            if cells:
                rows.append((rn, cells))
        return rows


def check_anchor(anchor, roots):
    parsed = split_anchor(anchor)
    if parsed is None:
        return "锚点格式非法：应为 位置 => \"摘抄\""
    pos, quote = parsed
    core = core_quote(quote)
    if not core:
        return "摘抄为空"
    core_n = norm(core)

    mx = XLSX_POS.match(pos)
    if mx:
        cands = find_candidates(mx.group("file"), roots)
        if not cands:
            return "未找到原文文件：{}".format(mx.group("file"))
        sheet = mx.group("sheet")
        c1, c2 = mx.group("cell"), mx.group("cell2")
        reasons = []
        for path in cands:
            try:
                rows = xlsx_rows(path, sheet)
            except ValueError as exc:
                reasons.append("{}: {}".format(path, exc))
                continue
            if c2:
                m1, m2 = re.match(r"([A-Za-z]+)(\d+)", c1), re.match(r"([A-Za-z]+)(\d+)", c2)
                col1, col2 = sorted([col_num(m1.group(1)), col_num(m2.group(1))])
                r1, r2 = sorted([int(m1.group(2)), int(m2.group(2))])
                texts = [t for rn, cells in rows if r1 <= rn <= r2
                         for col, t in cells.items() if col1 <= col_num(col) <= col2]
                loc = "{}#{}:{}".format(sheet, c1, c2)
            else:
                m = re.match(r"([A-Za-z]+)(\d+)", c1)
                col, rn = m.group(1).upper(), int(m.group(2))
                texts = [cells[col] for r, cells in rows if r == rn and col in cells]
                loc = "{}#{}".format(sheet, c1)
            if core_n and core_n in norm(" ".join(texts)):
                return None
            reasons.append("{}: {} 未匹配到摘抄".format(path, loc))
        return "；".join(reasons)

    dp = DOCX_POS.match(pos)
    if dp:
        cands = find_candidates(dp.group("file"), roots)
        if not cands:
            return "未找到原文文件：{}".format(dp.group("file"))
        num = int(dp.group("num"))
        section = dp.group("section")
        reasons = []
        for path in cands:
            try:
                paras = docx_paras(path)
            except Exception as exc:
                reasons.append("{}: 解析失败 {}".format(path, exc))
                continue
            if num < 1 or num > len(paras):
                reasons.append("{}: P{} 越界，共 {} 个非空段落".format(path, num, len(paras)))
                continue
            if core_n not in norm(paras[num - 1][1]):
                reasons.append("{}: P{} 内未匹配到摘抄".format(path, num))
                continue
            owner = docx_section_title(paras, num - 1)
            if section is not None and norm(section):
                if norm(section) != owner:
                    reasons.append("{}: P{} 所在节为「{}」，锚点标题「{}」不匹配".format(path, num, owner or "封面区", section))
                    continue
            elif owner:
                reasons.append("{}: P{} 在「{}」节内，锚点缺所在节标题".format(path, num, owner))
                continue
            return None
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

    if re.search(r"\.(pdf|ppt|pptx|doc|rtf|odt)\b", pos, re.IGNORECASE):
        return "原文类型不支持，请升级为澄清：{}".format(pos)
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
    """返回所有含必需列的表格，行合并为一张。
    澄清台账按两道澄清分两表或三表落盘，列相同，需全部读取以拿全 C 编号。"""
    matched = [(h, r) for h, r in parse_md_tables(text) if all(col in h for col in required)]
    if not matched:
        return None, None
    header = matched[0][0]
    rows = [row for _h, body in matched for row in body]
    return header, rows


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
