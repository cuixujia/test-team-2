---
description: 引文机验——TP/TC 送检前的机器校验（锚点真实性/摘抄匹配/TP关联/澄清编号）与 QA 的只读锚点检视。出处锚点格式的唯一口径在本 skill；生成、质检测试点与用例时均需按此校验
---

# 引文机验（citation-verify）

## 出处锚点格式（唯一口径，全团队照此）

| 原文类型 | 锚点格式 | 例 |
|---|---|---|
| md/txt/csv | `文件名:起始行[-结束行] => "摘抄"` | `prd1.md:12-15 => "客户名称长度不超过50个字符"` |
| docx | `文件名#章节标题 => "摘抄"` | `需求.docx#新增客户 => "保存成功后状态置为待审核"` |
| xlsx | `文件名#Sheet名!单元格 => "摘抄"` | `规则.xlsx#字段规则!B3 => "证件号为必填项"` |

规则：
- 摘抄从原文照抄，≤50 字（不含结尾截断符）；超出截断并以 `...` 结尾
- 摘抄内禁止半角双引号（原文如有换全角 `”`）、禁止 `|`、禁止 ` => `（无法避让时换选摘抄片段）
- 多个锚点写在一个单元格，用 ` ;; ` 分隔；单元格内容禁止出现 `|`
- docx 章节标题须对应原文的 Heading 样式段落（标题可只写标题核心词，允许包含匹配）
- xlsx 单元格坐标形如 `B3`（单格）；docx/xlsx 不转 md，机验现场抽取、用完即弃

## 经理送检前：verify_citation.py

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

校验项：①每条锚点位置真实存在（行区间不越界 / docx 章节可寻位 / xlsx 单元格有值）②摘抄与原文匹配（归一空白后子串比对，截断式摘抄按前缀匹配）且 ≤50 字 ③TC 的 `关联TP` 在 TP 清单存在 ④`澄清依据` 编号（`C-\d+`，可带 `(默认)`）在 clarifications.md 存在 ⑤TP/TC 编号格式合法 ⑥TC 对 TP 的覆盖缺口（无 TC 关联的 TP，仅警告）。

输出 JSON：`{"ok", "summary", "failures": [{record, field, anchor, reason}], "warnings": [...]}`。

通过标准：`failures` 为 0 才可送检（退出码 0）；`warnings` 逐条人工确认并把处置记入 state.md。退出码 1＝有失败项；2＝用法/结构致命错误（表头缺列、文件缺失等）。

`--out` 防护：输出文件名必须匹配 `citation-result*.json`，否则拒绝写入（防止脚本被挪作他用改写清单）。

## QA 抽验：inspect_anchor.py（只读，零写入能力）

```
python3 .opencode/skills/citation-verify/scripts/inspect_anchor.py \
  --docs <根>/project-docs --docs <会话>/user-input --anchor '<锚点>' [--anchor '<锚点2>' ...]
```

输出：每个锚点的解析结果、定位到的原文内容摘录、摘抄匹配判定。供 QA 在质检时逐条抽验 docx/xlsx 与可疑 md 锚点。

## 维护规则（唯一权威）

锚点语法、表格解析、摘抄归一化口径的任何改动，只改本目录 `scripts/` 三个文件（lib_citation.py 为核心实现，verify_citation.py / inspect_anchor.py 为入口），不得在其他 skill 或 agent 提示词中另写实现或复述判定逻辑。
