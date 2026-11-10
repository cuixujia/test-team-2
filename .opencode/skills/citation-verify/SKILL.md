---
description: 引文机验与产物格式契约——TP/TC 送检前的机器校验（锚点真实性/摘抄匹配/TP关联/澄清编号）、QA 的只读锚点检视，以及全团队产物锚点写法、clarifications 表、送检自校的唯一口径。生成、质检测试点与用例时均需按此校验
---

# 引文机验与产物格式契约（citation-verify）

## 锚点口径（唯一，全团队照此；TP / TC / clarifications / resources-index 四类产物通用）

| 原文类型 | 锚点格式 | 例 |
|---|---|---|
| md/txt/csv | `文件名:起始行[-结束行] => "摘抄"` | `prd1.md:12-15 => "客户名称长度不超过50个字符"` |
| docx | `文件名#章节标题 => "摘抄"` | `需求.docx#新增客户 => "保存成功后状态置为待审核"` |
| xlsx | `文件名#Sheet名!单元格 => "摘抄"` | `规则.xlsx#字段规则!B3 => "证件号为必填项"` |

规则：

1. 唯一口径：`文件名:行号 => "摘抄"`；多锚点写同一单元格用 ` ;; ` 分隔；单元格内容禁止出现 `|`（拆断列，机验判格式非法）。
2. 摘抄从原文照抄、≤50 字（不含结尾截断符）、须为定位行的**连续原文片段**（可去表格竖线压缩）；超出截断并以 `...` 结尾；禁止改写、缩合、空格补齐。
3. 摘抄内禁止半角双引号（原文如有换全角 `”`）、禁止 `|`、禁止 ` => `（无法避让时换选摘抄片段）。
4. 禁止裸格式 `文件名:行号`（无摘抄段）。
5. 横线/分隔符一律 ASCII 短横线 `-`；长横线 `—` 会被机验拒收（澄清依据列尤其注意）。
6. docx 章节标题须对应原文的 Heading 样式段落（标题可只写核心词，允许包含匹配）；xlsx 单元格坐标形如 `B3`（单格）；docx/xlsx 不转 md，机验现场抽取、用完即弃。
7. **写一条、当场验一条**：先跑 `inspect_anchor.py --help` 确认用法，写一条锚点就按该用法跑一次机验；攒批后补验视为违规。
8. 数值型具体值（字数/长度/个数/金额）落笔前逐字自校一遍（防"自称 25 字实为 17 字"类自相矛盾）。

## 清单表机器契约（列名与脚本 *_REQUIRED 逐字一致；语义判据在两 workflow skill，本节只载表面事实）

**TP 表 6 列**（`TP_REQUIRED`）：`编号 | 关联业务功能 | 测试点名称 | 类型 | 澄清依据 | 出处锚点`，取值详表见 skill `test-point-workflow`。

**TC 表 11 列**（`TC_REQUIRED`）：`编号 | 关联业务功能 | 关联TP | 用例名称 | 用例类型 | 前置条件 | 测试数据 | 操作步骤 | 预期结果 | 澄清依据 | 出处锚点`，取值详表见 skill `test-case-workflow`。

TP、TC 均**不设优先级列**，排序即优先级（承接两 workflow skill 的裁决口径）。

## clarifications 表（7 列，列名与 `CLAR_REQUIRED` 逐字一致）

```
编号 | 来源 | 问题 | 影响面 | 默认建议 | 答复 | 状态
```

| 字段 | 取值规则 |
|---|---|
| 编号 | `C-01` 起递增 |
| 来源 | QA 报告编号（如 `qa-materials.md R1 · Q-M-R1-C1`）或关口答复 |
| 影响面 | 写涉及条目的**当前**编号；条目重编号后**同步更新**（防指针漂移） |
| 默认建议 | 具体可执行、可直接转成断言口径；不可执行的不算默认建议 |
| 答复 | 可留空盛放原文答复 |
| 状态 | 仅 `待答复` / `默认生效` / `已答复` |

## 生成端送检前：verify_citation.py

阶段 3（TP 生成后）：

```
python3 .opencode/skills/citation-verify/scripts/verify_citation.py \
  --docs <根>/project-docs --docs <会话>/user-input \
  --tp <会话>/output/tp/list.md --clar <会话>/state/clarifications.md \
  --out <会话>/state/citation-result.json
```

阶段 5（TC 生成后，TP/TC 全参）：

```
python3 .opencode/skills/citation-verify/scripts/verify_citation.py \
  --docs <根>/project-docs --docs <会话>/user-input \
  --tp <会话>/output/tp/list.md --tc <会话>/output/tc/list.md \
  --clar <会话>/state/clarifications.md --out <会话>/state/citation-result.json
```

校验项：
1. 每条锚点位置真实存在（行区间不越界 / docx 章节可寻位 / xlsx 单元格有值）
2. 摘抄与原文匹配（归一空白后子串比对，截断式摘抄按前缀匹配）且 ≤50 字
3. TC 的 `关联TP` 在 TP 清单存在
4. `澄清依据` 编号（`C-\d+`，可带 `(默认)`）在 clarifications.md 存在
5. TP/TC 编号格式合法
6. TC 对 TP 的覆盖缺口检查（无 TC 关联的 TP，仅警告）

输出 JSON：`{"ok", "summary", "failures": [{record, field, anchor, reason}], "warnings": [...]}`。

通过标准：`failures` 为 0 才送检（退出码 0）；退出码 1＝有失败项，2＝用法/致命错误（表头缺列、文件缺失等）。`warnings` 逐条人工确认并把处置记入 state.md。

`--out` 防护：输出文件名必须匹配 `citation-result*.json`，否则拒绝写入（防止脚本被挪作他用改写清单）。

## 送检前自校（一次跑完，零才送检）

1. `verify_citation.py` 一次跑完 `--tp`/`--tc`/`--clar`，`failures` 与 `fatal_messages` 全零才送检；参数以脚本 `--help` 为准。
2. 逐列对照清单表机器契约：类型/用例类型/澄清依据/锚点格式白名单。
3. 表头列名与脚本 `*_REQUIRED` 逐字核对（改列名必须同步改脚本，且双向核对）。
4. 每条锚点已当场跑过 `inspect_anchor.py`（见"锚点口径"第 7 条）。

## QA 抽验：inspect_anchor.py（只读，零写入能力）

单行形态执行（与 qa-expert bash 白名单 `python3 *inspect_anchor.py*` 匹配，勿用 `\` 换行）：

```
python3 .opencode/skills/citation-verify/scripts/inspect_anchor.py --docs <根>/project-docs --docs <会话>/user-input --anchor '<锚点>' [--anchor '<锚点2>' ...]
```

输出：每个锚点的解析结果、定位到的原文内容摘录、摘抄匹配判定。供 QA 在质检时逐条抽验 docx/xlsx 与可疑 md 锚点。

## 维护规则（唯一权威）

锚点语法、表格解析、摘抄归一化口径的任何改动，只改本目录 `scripts/` 三个文件（lib_citation.py 为核心实现，verify_citation.py / inspect_anchor.py 为入口），不得在其他 skill 或 agent 提示词中另写实现或复述判定逻辑。
