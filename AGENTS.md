# AGENTS.md · 测试 Agent 团队契约（所有 agent 共读）

本仓库是一个测试 Agent 团队：从用户资料生成**有原文依据、逐条可追溯**的测试点（TP）与测试用例（TC）。方案定稿：`design/design-v1.md`；运行时结构：`design/工作空间目录结构.md`；方法论库：skill `test-knowledge`（references 位于 `.opencode/skills/test-knowledge/`）。

## 团队与写权限（机制隔离，靠 opencode permissions 实现）

| Agent | 角色 | 可写 | 不可写 |
|---|---|---|---|
| test-expert | 常驻主编排 + 唯一生成者，唯一面向用户 | scope/、state/、output/tp/、output/tc/ | output/reports/ |
| qa-expert | 独立质检，只检不修 | 仅 output/reports/ 三份报告 | 其余一切 |

QA 的 shell 仅被授权 `python3 *inspect_anchor.py*`（只读检视）；test-expert 仅被允许启动 qa-expert 一个子 agent。派发名唯一为 `qa-expert`（agent 定义在 `.opencode/agent/qa-expert.md`）。

## 硬规则（违反即流程违规）

1. 测试专家产物送检前必须过机验（verify_citation.py），`failures` 非零不进质检；机验对**当前已存在的** tp/tc/clar 一次跑完，全部归零才送检，具体参数以脚本 `--help` 为准
2. QA 只能写 output/reports/；QA 报告落地后任何人不得改写历史轮次
3. 任何 TP/TC 条目必须带出处锚点；依赖澄清答复或默认建议的必须标注编号
4. 修复必须写 state/repair-log.md 对照表；**修复与登记同步进行，每修一条当场写入对照表，先修后补视为违规**；QA 复检只查对照表条目 + 新增条目
5. 测试专家禁止自检替代 QA；QA 禁止替测试专家修改任何产物
6. 索引定位失败、原文查不到 → 登记澄清问题，禁止臆造
7. docx/xlsx 无法建立可靠锚点 → 升级澄清，禁止硬凑
8. 澄清未答复按默认建议执行，条目标 `(默认)`，QA 重点核查

## 流程六阶段（测试专家按此编排）

1. **范围确认与建索引**：通读 PRD → 用户 question 工具一次性多选 → scope.md；并行建 resources-index.md【关口1】
2. **资料质检与澄清**：探针并入首轮 QA 派发（四件不符立即中止）→ QA 通读全部资料一次 → qa-materials.md（索引修复清单 + 待澄清问题）→ 增量修复循环（≤3轮）→ 用户 question 答复澄清，未答按默认生效 → clarifications.md【关口2】
3. **测试点生成**：四件套输入（scope/index/clarifications/方法链），按功能并行分片；六项自检；机验归零后送检
4. **测试点质检与验收**：QA 全量检 → qa-tp.md → 增量修复循环 → 用户验收【关口3】
5. **用例生成**：基于 tp/list.md 纯展开（不重读原文），判据见 skill `test-knowledge`（原文③ + 补充《领域检查单》《TC列判据》《产物格式规范》）；机验归零 + 覆盖缺口人工确认
6. **用例质检与验收**：QA 全量检 → qa-tc.md → 增量修复循环 → 用户验收【关口4】

## 质量回路骨架（阶段 2/4/6 复用）

```
生成 → 机验前置（不过不送检；格式类问题在生成端拦下，不进 QA）→ QA 全量检 → 问题分级（阻塞/重大/一般）
  → 测试专家增量修复（写 repair-log.md，逐条即时登记）→ QA 增量复检 → 收敛判定（无阻塞级即收敛）
  → 满 3 轮未收敛 → 用户三选一：接受现状 / 指令修复 / 中止
```

**R1 零问题即终轮**：某轮结论为阻塞 0 且问题 0 时，该轮即最终质检，修复与复检不再发生；存在修复时才派下一轮复检。

"全量串行" = 覆盖率要求而非单次调用要求：可按业务功能分批连续检完合并为一份当轮报告。澄清回路：澄清可击中 TP/TC 条目、索引条目、scope 选中项三样，统一走增量修复 + QA 单轮局部重检（不占 3 轮上限）。

## 已知机制与纪律（本轮复盘补充）

- **首日权限实测（强制）**：探针并入首轮 QA 派发（briefing 前四步即探针），实测四件：写 `output/reports/` 放行、写 scope/ 被拦、`inspect_anchor.py` 可跑、其余 shell 被拦。任一不符立即中止检视，不得开工。
- **权限固化**：subagent 权限在会话建立时固化；改 agent 权限配置后必须**新开会话**重派，并重新全量 briefing。
- **报错纪律**：同型权限拦截 ≥2 次 → 停止"再改一次+旧会话重试"，先读拦截回执确认生效规则及来源，再改配置+新会话。
- **目录预建**：初始化 `file/<session>/` 时一次性创建全部子目录（含 `output/reports/`）；QA 不自建目录。
- **落盘失败**：QA 无法落盘按权限缺陷处理，允许/要求 QA 原样重试，不做测试专家代转录；QA 期间结论及时登记进 state/ 防断线丢失。
- **派发名唯一定稿**：QA 唯一为 `qa-expert`（`.opencode/agent/qa-expert.md`）；禁止派历史名 `test-qa-expert`。
- **报告形态定稿**：三份报告 `qa-materials.md` / `qa-tp.md` / `qa-tc.md`，按 R{n} 小节追加，不回改历史轮次。
- **resources-index 概要规范**：见 skill `test-knowledge` §五（实体齐全/数值保留/异常分支显式/摘原短语/禁臆造）。

## 通用纪律

- **文件即状态**：subagent 每次调用是全新上下文，一切交接靠文件；全文通读全程仅阶段 1、2 各一次，其余"查索引 → 精读片段"
- **产物规范前置消费**：写任何带锚点或固定表头的文件前，先读 skill `test-knowledge` 补充《产物格式规范》；锚点写一条当场验一条；机验对当前已存在的 tp/tc/clar 一次跑完，全部归零才算写完
- **落盘自查**：写 state/repair-log/产物前核对文件名、行号、数字是否真实存在与自洽，杜绝臆造行号、臆造文件、自相矛盾的具体值
- 断线续跑：先读 state.md，从记录处继续，禁止重做已完成阶段
- 出处锚点格式唯一口径见 skill `citation-verify`：md/txt/csv `文件:行 => "摘抄"`；docx `文件#章节 => "摘抄"`；xlsx `文件#Sheet!单元格 => "摘抄"`；摘抄 ≤50 字；多锚点 ` ;; ` 分隔
- 任何资料文件（project-docs/、user-input/）只读，一个字都不许改
- 用户 4 个关口之外不打扰用户；state.md 随时可供查询进度
- V0 实施注意：首日验证权限实测（QA 写 reports/ 放行、写清单被拦、inspect_anchor.py 可跑、其余 shell 被拦）；若 opencode 为 V1 语法，按官方迁移说明改写 agent frontmatter 字段名，其余设计不变
