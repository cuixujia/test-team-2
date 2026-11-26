# -*- coding: utf-8 -*-
"""机验脚本单元测试：验证 name/headers/rows 表格化产物的解析、结构校验与检查结论。

运行：python3 test_verify_citation.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "verify_citation.py")
sys.path.insert(0, HERE)

from lib_citation import json_table_with_lines


def make_docx(path, paras):
    """构建最小 docx 夹具：paras = [(style, text), ...]，style 为空串表示普通段落。"""
    import zipfile
    body = "".join(
        f'<w:p><w:pPr><w:pStyle w:val="{st}"/></w:pPr><w:r><w:t>{t}</w:t></w:r></w:p>'
        if st else f'<w:p><w:r><w:t>{t}</w:t></w:r></w:p>'
        for st, t in paras
    )
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as zh:
        zh.writestr("word/document.xml", doc)


def make_xlsx(path, sheets):
    """构建最小 xlsx 夹具：sheets = [(name, [(row_num, {col: text}), ...])]。"""
    import zipfile
    wb = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    for i, (name, _) in enumerate(sheets, 1):
        wb += f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        rels += f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="worksheets/sheet{i}.xml"/>'
    wb += '</sheets></workbook>'
    rels += '</Relationships>'
    with zipfile.ZipFile(path, "w") as zh:
        zh.writestr("xl/workbook.xml", wb)
        zh.writestr("xl/_rels/workbook.xml.rels", rels)
        for i, (_, rows) in enumerate(sheets, 1):
            ws = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            for rn, cells in rows:
                ws += f'<row r="{rn}">'
                for col, text in sorted(cells.items()):
                    ws += f'<c r="{col}{rn}" t="inlineStr"><is><t>{text}</t></is></c>'
                ws += '</row>'
            ws += '</sheetData></worksheet>'
            zh.writestr(f"xl/worksheets/sheet{i}.xml", ws)

TP_HEADERS = ["AI测试点编号", "系统功能", "测试点", "类型", "测试维度", "所属小类", "用例展开重点", "依据类型", "备注"]
# 需求两列 headers 恒含，机验只校验列存在不校验列值
TC_HEADERS = ["AI用例编号", "系统", "系统功能", "测试点", "用例名称", "优先级", "用例类型", "测试方法", "前置条件", "测试数据", "测试步骤", "预期结果", "依据类型", "备注", "需求分组名称", "需求名称", "是否可入库", "是否删除"]

# 原文固定三行可锚内容，行号 4/7/10
PRD_LINES = [
    "# PRD",
    "",
    "## 新增",
    "系统支持新增个人客户与对公客户",
    "",
    "## 表单",
    "表单字段：姓名、年龄",
    "",
    "## 保存",
    "保存成功后状态置为待审核",
]
A1 = 'prd1.md:4 => "系统支持新增个人客户与对公客户"'
A2 = 'prd1.md:7 => "表单字段：姓名、年龄"'
A3 = 'prd1.md:10 => "保存成功后状态置为待审核"'

CLAR_TEXT = """# 澄清记录

| 编号 | 来源 | 问题 | 影响面 | 默认建议 | 答复 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| C-01 | Q-M-R1-C01 | 状态口径 | F01 | 按 PRD | 接受默认建议 | 已答复 |
"""


def make_table(path, name, headers, rows, extra_blank=False):
    """按行写表格化 JSON：数据行从第 5 行起各占一行；extra_blank 在行间插空行验证行号定位。"""
    lines = ["{", '  "name": "%s",' % name, '  "headers": %s,' % json.dumps(headers, ensure_ascii=False), '  "rows": [']
    for i, r in enumerate(rows):
        comma = "," if i < len(rows) - 1 else ""
        if extra_blank and i > 0:
            lines.append("")
        lines.append("    %s%s" % (json.dumps(r, ensure_ascii=False), comma))
    lines += ["  ]", "}"]
    write_text(path, "\n".join(lines))


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read_rows(path):
    """读取表格化产物的 rows 数据，供变体场景改写。"""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["rows"]


def tp_row(tid, tname, sub, basis="原文依据", anchors=None):
    return [tid, "F01 新增", tname, "功能级", "基础功能", sub, ["分支一", "分支二"], basis, anchors or [A1]]


def tc_row(tcid, tp_ref, tname, data, steps, expect, anchors=None, basis="原文依据"):
    # 末四列为需求两列与固定值两列，与 TC_HEADERS 对齐
    return [tcid, "客户管理系统", "F01 新增", tp_ref, tname, "高", "功能用例", "等价类+边界值", "已登录", data, steps, expect, basis, anchors or [A1], "协同平台", "客户需求管理二期", "是", "否"]


class Env(unittest.TestCase):
    """公共夹具：临时目录内准备原文、澄清表与默认全绿的 TP/TC 产物。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.docs = os.path.join(self.root, "project-docs")
        os.makedirs(self.docs)
        write_text(os.path.join(self.docs, "prd1.md"), "\n".join(PRD_LINES))
        self.clar = os.path.join(self.root, "clarifications.md")
        write_text(self.clar, CLAR_TEXT)
        self.tp_path = os.path.join(self.root, "tp-F01.json")
        self.tc_path = os.path.join(self.root, "tc-F01.json")
        self.write_tp()
        self.write_tc()

    def tearDown(self):
        self._tmp.cleanup()

    def write_tp(self, rows=None):
        if rows is None:
            rows = [
                tp_row("TP-001", "验证界面展示", "功能正确性"),
                tp_row("TP-002", "验证正常新增", "功能正确性", basis="澄清依据(C-01)", anchors=[A3]),
                tp_row("TP-003", "验证字段约束", "字段校验", basis="补充条目", anchors=[A2]),
            ]
        make_table(self.tp_path, "F01-TP", TP_HEADERS, rows)

    def write_tc(self, rows=None):
        if rows is None:
            rows = [
                tc_row("TC-001", "TP-001 验证界面展示", "验证布局正确", "无", ["1.打开页面"], "布局符合"),
                tc_row("TC-002", "TP-001 验证界面展示", "验证元素齐全", "字段=全量", ["1.打开页面", "2.核对元素"], "元素齐全"),
                tc_row("TC-003", "TP-002 验证正常新增", "验证必填新增成功", "姓名=张三", ["1.填写", "2.保存"], "保存成功"),
                tc_row("TC-004", "TP-002 验证正常新增", "验证状态落库", "姓名=李四", ["1.填写", "2.保存", "3.查库"], "状态=待审核"),
                tc_row("TC-005", "TP-003 验证字段约束", "验证超长拦截", "姓名=51字符", ["1.填写", "2.保存"], "拦截超长"),
                tc_row("TC-006", "TP-003 验证字段约束", "验证特殊字符拦截", "姓名=含空格", ["1.填写", "2.保存"], "拦截非法"),
            ]
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)

    def run_verify(self, *args):
        """子进程跑机验，返回 (退出码, payload)。"""
        p = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, encoding="utf-8")
        return p.returncode, json.loads(p.stdout)

    def verify_tp_tc(self, extra=()):
        return self.run_verify("--docs", self.docs, "--tp", self.tp_path, "--tc", self.tc_path, "--clar", self.clar, *extra)


class TestJsonTableWithLines(unittest.TestCase):
    """lib 层结构解析单测。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "tp-F01.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_normal_and_line_numbers(self):
        rows = [["TP-001", "a"], ["TP-002", "b"]]
        make_table(self.path, "F01-TP", ["编号", "x"], rows)
        name, headers, got, marks, err = json_table_with_lines(self.path)
        self.assertIsNone(err)
        self.assertEqual(name, "F01-TP")
        self.assertEqual(headers, ["编号", "x"])
        self.assertEqual(got, rows)
        self.assertEqual(marks, [5, 6])  # 数据行从第 5 行起各占一行

    def test_blank_line_does_not_shift_ids(self):
        rows = [["TP-001", "a"], ["TP-002", "b"]]
        make_table(self.path, "F01-TP", ["编号", "x"], rows, extra_blank=True)
        _n, _h, _r, marks, err = json_table_with_lines(self.path)
        self.assertIsNone(err)
        self.assertEqual(marks, [5, 7])  # 空行跳过后行号仍指向真实数据行

    def test_rejects_bad_structures(self):
        cases = {
            "空文件": "",
            "非法JSON": "{oops",
            "顶层为数组": "[]",
            "缺name": '{"headers": ["a"], "rows": [["x"]]}',
            "headers非数组": '{"name": "F01-TP", "headers": "a", "rows": []}',
            "headers含空串": '{"name": "F01-TP", "headers": [""], "rows": []}',
            "缺rows": '{"name": "F01-TP", "headers": ["a"]}',
            "行非数组": '{"name": "F01-TP", "headers": ["a"], "rows": ["x"]}',
            "行长不匹配": '{"name": "F01-TP", "headers": ["a", "b"], "rows": [["x"]]}',
        }
        for label, text in cases.items():
            write_text(self.path, text)
            _n, _h, _r, _m, err = json_table_with_lines(self.path)
            self.assertIsNotNone(err, label)


class TestEndToEnd(Env):
    """端到端：新格式产物的检查结论与退出码。"""

    def test_all_green(self):
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["tp_rows"], 3)
        self.assertEqual(payload["summary"]["tc_rows"], 6)
        self.assertEqual(payload["failures"], [])

    def test_entry_lines_match_physical_lines(self):
        _code, payload = self.verify_tp_tc()
        self.assertEqual(payload["entry_lines"]["tp-F01.json"], {"TP-001": 5, "TP-002": 6, "TP-003": 7})
        self.assertEqual(payload["entry_lines"]["tc-F01.json"], {"TC-00%d" % i: 4 + i for i in range(1, 7)})

    def test_dup_case_detected(self):
        base = read_rows(self.tc_path)
        dup = list(base[4])
        dup[0] = "TC-007"
        make_table(self.tc_path, "F01-TC", TC_HEADERS, base + [dup])
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        dups = [f for f in payload["failures"] if f["field"] == "用例重复"]
        self.assertEqual(len(dups), 1)
        self.assertIn("TC-005", dups[0]["record"])
        self.assertIn("TC-007", dups[0]["record"])

    def test_tp_without_tc_warns(self):
        make_table(self.tc_path, "F01-TC", TC_HEADERS, self.tc_default_rows()[:2])
        code, payload = self.run_verify("--docs", self.docs, "--tp", self.tp_path, "--tc", self.tc_path, "--clar", self.clar)
        self.assertEqual(code, 0)
        warns = [w["record"] for w in payload["warnings"] if "无任何关联用例" in w["reason"]]
        self.assertTrue(any("TP-002" in r for r in warns))
        self.assertTrue(any("TP-003" in r for r in warns))

    def tc_default_rows(self):
        return read_rows(self.tc_path)

    def test_single_tc_breaks_conservation(self):
        rows = self.tc_default_rows()[:1]
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        self.assertTrue(any(f["field"] == "用例数量" for f in payload["failures"]))

    def test_bad_name_fatal(self):
        make_table(self.tp_path, "TP-F01", TP_HEADERS, read_rows(self.tp_path))
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 2)
        self.assertTrue(any("name 命名非法" in m for m in payload["fatal_messages"]))

    def test_missing_headers_field_fatal(self):
        bad = [h for h in TP_HEADERS if h != "类型"]
        rows = [r[:5] + r[6:] for r in read_rows(self.tp_path)]
        make_table(self.tp_path, "F01-TP", bad, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 2)
        self.assertTrue(any("headers 缺少必需字段" in m for m in payload["fatal_messages"]))

    def test_tc_missing_req_columns_fatal(self):
        # 需求两列缺失即致命，列值不校验
        bad = [h for h in TC_HEADERS if h not in ("需求分组名称", "需求名称")]
        rows = [r[:14] + r[16:] for r in read_rows(self.tc_path)]
        make_table(self.tc_path, "F01-TC", bad, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 2)
        self.assertTrue(any("headers 缺少必需字段" in m for m in payload["fatal_messages"]))

    def test_tc_req_columns_content_not_checked(self):
        # 需求列值任意不报错，机验不管内容
        rows = read_rows(self.tc_path)
        rows[0][14], rows[0][15] = "", ""
        rows[1][14], rows[1][15] = "其他分组", "其他需求"
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])

    def test_tc_yesno_columns_enforced(self):
        # 是否可入库/是否删除 取值须在枚举 是/否 内，越枚举即判失败
        rows = read_rows(self.tc_path)
        rows[0][16] = "可入库"   # 是否可入库 越枚举
        rows[1][17] = ""          # 是否删除 空值越枚举
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        fields = {f["field"] for f in payload["failures"]}
        self.assertTrue({"是否可入库", "是否删除"} <= fields)

    def test_tc_yesno_swapped_values_ok(self):
        # 用户逐条改值：与默认相反但仍是合法枚举，机验放行
        rows = read_rows(self.tc_path)
        rows[0][16] = "否"   # 是否可入库 改否
        rows[1][17] = "是"   # 是否删除 改是
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])

    def test_old_format_fatal(self):
        write_text(self.tp_path, json.dumps({"清单类型": "测试点清单", "测试点": [{"编号": "TP-001"}]}, ensure_ascii=False))
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 2)
        self.assertTrue(any("缺少字符串字段 `name`" in m for m in payload["fatal_messages"]))

    def test_tc_without_tp_fatal(self):
        code, payload = self.run_verify("--docs", self.docs, "--tc", self.tc_path)
        self.assertEqual(code, 2)

    def test_anchor_mismatch_fails(self):
        rows = read_rows(self.tp_path)
        rows[0][-1] = ['prd1.md:4 => "不存在的摘抄"']
        make_table(self.tp_path, "F01-TP", TP_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        self.assertTrue(any(f["field"] == "备注" for f in payload["failures"]))

    def test_unknown_clar_ref_fails(self):
        rows = read_rows(self.tp_path)
        rows[0][7] = "澄清依据(C-99)"
        rows[1][7] = "方法论补充"
        make_table(self.tp_path, "F01-TP", TP_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        basis_fails = [f for f in payload["failures"] if f["field"] == "依据类型"]
        self.assertEqual(len(basis_fails), 2)
        self.assertTrue(any("C-99" in f["reason"] for f in basis_fails))
        self.assertTrue(any("依据类型非法" in f["reason"] for f in basis_fails))

    def test_tc_new_columns_enforced(self):
        rows = read_rows(self.tc_path)
        rows[0][1] = ""      # 系统置空
        rows[0][5] = "紧急"   # 优先级越枚举
        rows[0][6] = "正向"   # 用例类型旧值不再合法
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        fields = {f["field"] for f in payload["failures"]}
        self.assertTrue({"系统", "优先级", "用例类型"} <= fields)

    def test_tc_basis_merged_column_checked(self):
        rows = read_rows(self.tc_path)
        rows[0][12] = "澄清依据(C-01)"   # 合法引用，编号存在
        rows[1][12] = "澄清依据(C-99)"   # 编号不存在
        rows[2][12] = "方法论补充"       # 旧值不再合法
        rows[3][12] = "补充条目"         # 合法
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        basis_fails = [f for f in payload["failures"] if f["field"] == "依据类型"]
        self.assertEqual(len(basis_fails), 2)
        self.assertTrue(any("C-99" in f["reason"] for f in basis_fails))
        self.assertTrue(any("依据类型非法" in f["reason"] for f in basis_fails))

    def test_tc_remark_anchor_checked(self):
        rows = read_rows(self.tc_path)
        rows[0][13] = ['prd1.md:4 => "不存在的摘抄"']
        rows[1][13] = []
        make_table(self.tc_path, "F01-TC", TC_HEADERS, rows)
        code, payload = self.verify_tp_tc()
        self.assertEqual(code, 1)
        remarks = [f for f in payload["failures"] if f["field"] == "备注"]
        self.assertEqual(len(remarks), 2)

    def test_missing_clar_file_fatal(self):
        code, payload = self.run_verify("--docs", self.docs, "--tp", self.tp_path, "--clar", os.path.join(self.root, "nope.md"))
        self.assertEqual(code, 2)


class TestIndexMode(Env):
    """索引域机验：锚点抽验与新格式无耦合，回归确认未被改坏。"""

    def write_index(self, anchor):
        path = os.path.join(self.root, "resources-index.md")
        write_text(path, "# 资料索引\n\n## prd1.md\n\n### 新增\n\n- 锚点：%s\n" % anchor)
        return path

    def test_index_anchor_ok(self):
        path = self.write_index(A1)
        code, payload = self.run_verify("--docs", self.docs, "--index", path)
        self.assertEqual(code, 0)
        self.assertEqual(payload["summary"]["index_anchors"], 1)

    def test_index_anchor_bad(self):
        path = self.write_index('prd1.md:4 => "不存在"')
        code, payload = self.run_verify("--docs", self.docs, "--index", path)
        self.assertEqual(code, 1)
        self.assertEqual(payload["failures"][0]["record"], "resources-index")


class TestOfficeAnchors(Env):
    """Office 锚点：docx P 号与 xlsx 新语法，TP-only 模式只验锚点不涉用例守恒。"""

    def setUp(self):
        super().setUp()
        self.docx_path = os.path.join(self.docs, "prd.docx")
        make_docx(self.docx_path, [
            ("Heading1", "产品需求说明书"),
            ("Heading2", "1. 文档元信息"),
            ("", "需求创建后进入待沟通状态"),
            ("Heading2", "2. 业务流程"),
            ("", "派发后进入处理中"),
        ])
        self.xlsx_path = os.path.join(self.docs, "data.xlsx")
        make_xlsx(self.xlsx_path, [
            ("功能清单", [
                (1, {"A": "编号", "B": "名称"}),
                (2, {"A": "F01", "B": "需求创建"}),
                (3, {"A": "F02", "B": "需求派发"}),
            ])
        ])

    def verify_tp_anchor(self, anchor):
        """把默认 TP 首行锚点换成待测锚点，跑 TP-only 机验。"""
        rows = read_rows(self.tp_path)
        rows[0][-1] = [anchor]
        make_table(self.tp_path, "F01-TP", TP_HEADERS, rows)
        return self.run_verify("--docs", self.docs, "--tp", self.tp_path, "--clar", self.clar)

    def test_docx_anchor_ok(self):
        code, payload = self.verify_tp_anchor('prd.docx:P3#1. 文档元信息 => "需求创建后进入待沟通状态"')
        self.assertEqual(code, 0, payload["failures"])

    def test_docx_title_mismatch(self):
        code, payload = self.verify_tp_anchor('prd.docx:P3#2. 业务流程 => "需求创建后进入待沟通状态"')
        self.assertEqual(code, 1)
        self.assertTrue(any("所在节" in f["reason"] for f in payload["failures"]))

    def test_docx_excerpt_mismatch(self):
        code, payload = self.verify_tp_anchor('prd.docx:P3#1. 文档元信息 => "派发后进入处理中"')
        self.assertEqual(code, 1)
        self.assertTrue(any("未匹配到摘抄" in f["reason"] for f in payload["failures"]))

    def test_docx_missing_title(self):
        code, payload = self.verify_tp_anchor('prd.docx:P3 => "需求创建后进入待沟通状态"')
        self.assertEqual(code, 1)
        self.assertTrue(any("缺所在节标题" in f["reason"] for f in payload["failures"]))

    def test_docx_out_of_range(self):
        code, payload = self.verify_tp_anchor('prd.docx:P999#1. 文档元信息 => "需求创建后"')
        self.assertEqual(code, 1)
        self.assertTrue(any("越界" in f["reason"] for f in payload["failures"]))

    def test_docx_old_format_unsupported(self):
        code, payload = self.verify_tp_anchor('prd.docx#1. 文档元信息 => "需求创建后进入待沟通状态"')
        self.assertEqual(code, 1)
        self.assertTrue(any("格式不识别" in f["reason"] for f in payload["failures"]))

    def test_xlsx_single_cell_ok(self):
        code, payload = self.verify_tp_anchor('data.xlsx:功能清单#B2 => "需求创建"')
        self.assertEqual(code, 0, payload["failures"])

    def test_xlsx_range_ok(self):
        code, payload = self.verify_tp_anchor('data.xlsx:功能清单#A2:B3 => "F01"')
        self.assertEqual(code, 0, payload["failures"])

    def test_xlsx_excerpt_mismatch(self):
        code, payload = self.verify_tp_anchor('data.xlsx:功能清单#B2 => "需求派发"')
        self.assertEqual(code, 1)
        self.assertTrue(any("未匹配到摘抄" in f["reason"] for f in payload["failures"]))

    def test_xlsx_sheet_not_found(self):
        code, payload = self.verify_tp_anchor('data.xlsx:不存在的Sheet#A1 => "编号"')
        self.assertEqual(code, 1)
        self.assertTrue(any("未找到Sheet" in f["reason"] for f in payload["failures"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
