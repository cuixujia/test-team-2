# 测试用例生成团队（.opencode）规则审查与优化报告

审查对象：`.opencode/agent/` 4 个角色配置、`.opencode/skills/` 4 个 skill、机验脚本 3 个、`tool/show_artifact.ts`。
审查方式：全文通读 + 交叉引用核对 + 实际运行验证（段级索引行号逐段抽查、机验单测 20/20 通过、`python3` 可用、`show_artifact` 支持目录入参、PowerShell 命令实测）。

---

## 一、规则冲突与影响 AI 判断的问题

按影响程度排序，★ 为高危（会直接导致流程走偏、额外轮次或阻塞）。

### C1 ★ scope.md 的写入者前后矛盾

- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L42) 第 42 行：「原文读取、**范围单**与索引落盘……全部派发给子 agent」
- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L209) 产物结构注释：`scope.md # 范围确认单，资料专家写`
- 但 [阶段 2.3](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L131) 明确由**经理**落盘 scope.md，且经理 write 权限含 `scope/scope.md`；而 [material-expert.md](file:///d:/Project/test-team-2/.opencode/agent/material-expert.md#L2) 自述「**不写范围单**」。

影响：两处说资料专家写、两处说经理写，且资料专家被自己的描述禁止写。关口 1 答复只有经理能看到，实际只能经理写。AI 命中哪条取决于上下文顺序，不可控。
建议：统一为「经理写」。改 L42 删去「范围单」、L209 注释改「经理写」；同时把资料专家 write 权限从 `scope/**` 收紧为 `scope/resources-index.md`，消除误写通道。

### C2 ★ 子 agent 拿不到 SKILLS_ROOT，机验命令无法拼出

- 机验命令模板含 `SKILLS_ROOT` 占位（[quality-check SKILL.md](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L83-L88)）
- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L202)：SKILLS_ROOT 写在 `state/briefing.md`
- 但 [任务派发表](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L101-L104) 对 `TP-生成`/`TC-生成` 明确「**不读 briefing.md**」；qa-expert 的[委派项](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L33)也不含 briefing 或 SKILLS_ROOT；经理委派通则要求的 prompt 必写项里同样没有 SKILLS_ROOT。

影响：测试专家与质检专家需要跑机验却被切断唯一获取 SKILLS_ROOT 的路径，只能额外探索（glob 找 skill 目录）或阻塞，违背「禁止新增工具回合」。只有索引构建（读 briefing.md）能拿到。
建议（三选一，推荐 1）：
1. 在 quality-check【机验说明】写死推导规则：`SKILLS_ROOT = <工作空间根>/.opencode/skills`，占位符即可由委派项中的工作空间根直接解析；
2. 委派项增加一行「SKILLS_ROOT：绝对路径」；
3. 放开 TP/TC 生成任务读 briefing.md（与省 token 初衷冲突，不推荐）。

### C3 ★ TC 生成/修复会话未加载 test-knowledge-canon，却要求按段索引读知识

- [test-expert.md](file:///d:/Project/test-team-2/.opencode/agent/test-expert.md#L41-L42)：`TC-生成`/`TC-修复` 加载清单为 test-point-workflow、test-case-workflow、quality-check，**无 canon**
- 但同文件[知识段路由表](file:///d:/Project/test-team-2/.opencode/agent/test-expert.md#L70-L73)要求 TC 必读「规则维度映射」段、按小类读关注点段——**行号只存在于 canon 的段级索引**，且 TC 会话与 TP 会话不同（[会话复用](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L79-L87)），无法复用 TP 会话已加载的 canon。

影响：TC 会话要么整读 `3通用测试规则.md`（618 行，token 大户），要么 grep 探索（额外轮次），两条路都违背设计意图。
建议：TC 生成/修复的加载清单补上 `test-knowledge-canon`（仅 111 行指针文件，成本远低于一次整读）；或把 TC 需要的行段（规则维度映射 585-618）直接内联进 test-case-workflow。

### C4 ★ QA 被禁加载 canon，判据却引用知识正文且无行号

- [qa-expert.md](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L41)：「禁止加载 `test-knowledge-canon`」
- 但 [quality-check TP 域](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L131) 颗粒度基准「按《测试点生成指南》四、4.1」、[TC 域](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L144) 边界值「按《通用测试方法论》五、5.1.2 六点法」——QA 需要读这两段原文才能判，而委派路径不含 references、无行号可 offset/limit 定位。

影响：QA 只能整读 528/422 行的知识文件，token 消耗最大的破口恰在被禁止处。
建议：在 quality-check 两处判据后直接内联行段：颗粒度基准＝`4测试点生成指南.md:115-143`、六点法＝`1通用测试方法论.md:87-113`（已实测核对）。一行改动，同时解除对 canon 的隐性依赖。

### C5 ★ 经理写死的回合结构与 qa-expert R1 自身约束冲突

- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L52-L57)：每个 task prompt 必须写死「1 加载读取 → 2 落盘 → **3 机验** → 4 回报」
- 但 [qa-expert.md](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L49) R1 是「第 1 回合……**再跑一次机验**」，机验在语义验与写报告**之前**。

影响：经理给质检任务的 prompt 会写一个 QA 必须违反的回合结构；QA 服从 prompt 还是服从自身约束不确定。
建议：经理模板第 3 步改为「机验时机按子 agent 各自回合约束执行，每轮每产物只跑一次」。

### C6 ★ R2 复检复用 R1 的 entry_lines，但修复后行号可能已位移

- [qa-expert.md](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L55)：R2「产物条目行复用 R1 机验输出的 entry_lines」
- 但 [test-point-workflow](file:///d:/Project/test-team-2/.opencode/skills/test-point-workflow/SKILL.md#L63) 编号规则「删除留空号」——删除条目会使**其后所有条目物理行上移**，R1 的行号映射即失效；新增条目在文件末尾追加则无影响。

影响：R2 按过期行号读条目，可能读错行、误判「未修复/新增问题」，触发无谓的第 3 轮。
建议（二选一）：
1. 修复任务回报协议增加一项：「删除条目时回报其后位移的条目编号→新行号差值」，经理转写入 repair-log 小节；
2. 放开 R2 跑一次机验仅为刷新 entry_lines（每轮每批多一次 bash 调用，换判定确定性）。

### C7 ★ `date +%Y%m%d-%H%M%S` 在 Windows PowerShell 下必然报错

- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L124) 阶段 1.3 用 bash `date +%Y%m%d-%H%M%S`；bash 权限仅放行 `pwd/ls/date`。
- 实测本机（PowerShell 5）：`Get-Date : 无法绑定参数"Date"……` 直接失败。

影响：每次新建会话第一轮工具调用即报错，产生一次失败重试轮；若模型改用 `Get-Date` 又会被 `date*` 之外的权限拦截。
建议：命令改为 `Get-Date -Format 'yyyyMMdd-HHmmss'`，权限同步放行 `Get-Date*`；或权限允许时由 briefing 记录环境差异。

### C8 「先修复后补记日志视为违规」与循环顺序自相矛盾

- [test-manager.md](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L186-L188)：循环顺序是「派修复 → 收修复回报 → **写 repair-log** → 派复检」，repair-log 的改动行号本来就来自修复回报，必然「先修复后补记」。
- 紧跟一句「先修复后补记日志视为违规」，字面上禁止的正是流程自身。

影响：经理在「决定修复范围」后可能犹豫是否要先写一版空日志，或复检前反复核日志时序。
建议：改为「**未落 repair-log 不得派发复检**」。

### C9 「机验覆盖……守恒问题不复核」与 TC 域展开完整性冲突

- [qa-expert.md](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L73) 工作步骤 2：「机验覆盖的锚点、结构、值域、关联、**守恒**、重复问题不复核、不入报告」
- 但 [quality-check TC 域](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L144) 展开完整性要求「逐主 TP 按守恒表**核算形态条数**，实际明显低于核算线即整批欠展开」——机验只查每 TP ≥2 条硬下限，客观分支计数只能语义验做。

影响：QA 按字面「守恒不复核」会整体跳过 TC 域最核心的展开完整性维度，或每次重新解释规则消耗推理。
建议：改为「机验覆盖的**每 TP 直属 ≥2 下限**不复核；形态条数的客观计数仍按 TC 域判据核算」。

### C10 资料专家 write 权限与自身规则不一致（低风险）

- [material-expert.md](file:///d:/Project/test-team-2/.opencode/agent/material-expert.md#L14-L20)：write/edit 放行整个 `scope/**`，但描述与生成规则均称不写范围单。权限比规则宽，存在误写通道（见 C1 联动）。
- [test-expert.md](file:///d:/Project/test-team-2/.opencode/agent/test-expert.md#L15-L22)：`TC-修复` 只产 tc 文件，但 write 含 `output/tp/**`；且 TC 域域边界禁止改 TP，权限与判据方向相反。

建议：按任务域收紧权限，或在规则中注明「tp 写权限仅 TP 任务使用」。

---

## 二、歧义表述（不阻塞但增加模型解释成本）

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| A1 | [quality-check L68](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L68) | 「禁裸格式 `文件名:行号`」——但示例与脚本均允许单行锚点 `prd1.md:5 => "…"`（[test-point-workflow L42](file:///d:/Project/test-team-2/.opencode/skills/test-point-workflow/SKILL.md#L42)、MD_POS 正则 end 可选）。疑义：禁的是单行还是禁无摘抄？ | 改为「禁无 ` => "摘抄"` 的裸位置；单行可省略结束行」 |
| A2 | [quality-check L16](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L16) | 「两档分级间难区分时**取低档**」——低档=较轻（一般）还是排序靠下？方向不明，直接影响收敛判定 | 明确「取较轻一档」 |
| A3 | [test-point-workflow L69](file:///d:/Project/test-team-2/.opencode/skills/test-point-workflow/SKILL.md#L69) | 「数组，2~3 项**以上**」自相矛盾 | 改「≥2 项，一般 2~4 项」 |
| A4 | [clarifications 字段表](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L397) 与 [quality-check L122-L123](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L122-L123) | QA 编号 `Q-M-R{N}-C{seq}` 与台账 `C-01` 的映射、R2+ 轮 seq 是否续接未定义 | 补一句「C-NN 与 Q-M-R{N}-C{seq} 按登记顺序一一对应，seq 跨轮全局续接」 |
| A5 | [qa-expert L2/L29](file:///d:/Project/test-team-2/.opencode/agent/qa-expert.md#L2) | 「只写三份报告」——按批次实为 1+N+N 个文件 | 改「三类报告（材料 1 份、TP/TC 每批各 1 份）」 |
| A6 | [test-manager L176](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L176) | 关口 1 选项「前 N 个 / 模块X内所有」是占位符，N、X 未定义 | 改「按清单规模给 1~2 个前缀子集选项」 |
| A7 | [test-manager L284/L293](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L293) | briefing「资料文件逐份写内容概要」，但经理不读 project-docs，概要来源未指定 | 注明「概要取自功能识别回报」 |
| A8 | [canon L37](file:///d:/Project/test-team-2/.opencode/skills/test-knowledge-canon/SKILL.md#L37) | 别名「测试方法分类 57-290」实际只覆盖 5.1 黑盒；5.2 白盒（291-399）未编目。别名与真标题「四、测试技术分类」（5-54 行）撞名 | 改别名「黑盒方法详解」，白盒不收录属有意设计可加注 |
| A9 | [quality-check L150](file:///d:/Project/test-team-2/.opencode/skills/quality-check/SKILL.md#L150) | 「阻塞，**随机验** failures」措辞生涩 | 改「阻塞级，以机验 failures 为准」 |
| A10 | [test-manager L202](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L202) | SKILLS_ROOT「由阶段 1 写入 briefing」，但经理如何得到该路径无规则（经理不读 skill） | 与 C2 合并解决：写死推导规则 `<根>/.opencode/skills` |

---

## 三、优化空间（降 token / 降耗时 / 降轮次）

### 3.1 提示词结构与精简

| # | 优化点 | 做法 | 预期收益 |
|---|---|---|---|
| O1 | **经理 prompt 模板段压缩**（最大杠杆） | 五个文件模板节（L227-L403，约 175 行）中字段要求表与骨架示例大量重复——骨架已展示格式，表内多为可推断的复述。将每节字段表压成骨架内行内注释，预计 175→90 行 | 经理 prompt 每轮随上下文重发，一次会话经理回合数最多（派发+回收+落盘）。按 40+ 经理回合计，约省 30-40% 经理侧输入 token |
| O2 | 派发表去重复括注 | 「（按索引定位本批章节）」在表内出现 5 次，[委派通则 L50](file:///d:/Project/test-team-2/.opencode/agent/test-manager.md#L50) 已总述。删表内括注，通则保留一句 | 减约 10 行，消除同义反复引发的优先级困惑 |
| O3 | 知识段路由与 canon 装配规则去重 | [test-expert L70-L77](file:///d:/Project/test-team-2/.opencode/agent/test-expert.md#L70-L77) 与 [canon 装配规则](file:///d:/Project/test-team-2/.opencode/skills/test-knowledge-canon/SKILL.md#L21-L27) 重复描述命中数→读段策略，两处措辞略有出入（1~3 vs 1~2） | 只留 canon 一处，test-expert 表格引用之；消除数字口径不一致的判定摇摆 |
| O4 | quality-check 内部去重 | 【通用纪律】与【报告结构】表重复「报告只追加」「机验覆盖不重入」等 3 条 | 合并，skill 减约 15% |
| O5 | 删除 `--out` 死参数 | 脚本已注释掉落盘（[verify_citation.py L387-L389](file:///d:/Project/test-team-2/.opencode/skills/quality-check/scripts/verify_citation.py#L387-L389)），SKILL 也声明「不落盘」，但命令表 4 条仍带 `--out`、两个子 agent 仍保留 `citation-result.json` 写权限、脚本仍校验 OUT_NAME | 每条机验命令短一截；删 2 处权限与 1 处校验分支；docstring 同步（当前 docstring 仍写「结果 JSON 落盘路径」，与实现矛盾） |

### 3.2 降模型调用轮次

| # | 优化点 | 做法 | 预期收益 |
|---|---|---|---|
| O6 | 修复 C2/C3/C4 | 见上文。每处不修，子 agent 平均多 1-2 个探索/失败回合；C7 的 date 失败每次新建会话必现 | 每会话省 5-10 个无效回合 |
| O7 | 小批量双文件并写 | test-expert 落盘「一回合只写一个功能文件」改为「单文件 ≤30 条时允许同回合并行写本批 2 个文件」 | 每批 TP/TC 生成各省 1 回合；大文件仍拆分保输出上限 |
| O8 | QA 报告一次成稿 | qa-expert R1「每回合只检一个文件并追加写报告」——批内仅 2 文件且问题少时，允许末回合一次追加两文件问题 | 每批每轮省 1 回合（保留长报告拆分选项） |
| O9 | 两道澄清合并（需确认） | 阶段 3 两道澄清现为 2 次 question + 2 个落盘节点；当两类合计 ≤4 题时选项集不同仍可同调用（question 支持逐题选项）。**现规则明确「不合并」，属有意设计**，改动需你确认 | 省 1 回合 + 1 落盘 |
| O10 | 阶段 1 环境自检并入 | 把「date 命令可用性、python3 可用性」检查并入阶段 1 已有的 ls/glob 回合，结论写 briefing | 防中流程失败重试 |

### 3.3 执行性能（脚本侧）

| # | 优化点 | 现状 | 做法 | 收益 |
|---|---|---|---|---|
| O11 | 文件索引缓存 | [find_candidates](file:///d:/Project/test-team-2/.opencode/skills/quality-check/scripts/lib_citation.py#L95-L109) 对**每个锚点**都 `os.walk` 全部 docs 目录；`read_lines`/`docx_paragraphs` 每锚点重复读盘解析 | 模块级 dict 缓存：文件名→路径列表、文件路径→行列表/段落列表，一次 walk 全程复用 | 机验从 O(锚点数×文件数) 降到 O(文件数)。数百锚点时墙钟时间降一个量级，且零行为变化（单测可回归） |
| O12 | entry_lines 载荷瘦身 | 全量条目行号打印到 stdout，TP+TC 各文件全部条目进上下文 | 可选 `--lines-only <编号列表>` 供 R2 场景；或保持现状（信息对语义验有用） | 每批省约 1-3K token，视条目规模 |

### 3.4 已验证无问题的项（免重复排查）

- **段级索引行号**：4 个 references 文件总行数（422/176/618/528）与索引上限一致；②③④ 全部子段与真实标题逐段抽查吻合，无过期行号。
- **机验脚本**：20 个单测全部通过；`python3` 在本机可用（D:\python\python3139）。
- **show_artifact**：支持目录入参，与经理阶段 5.2/7.2 用法一致。
- **编号体系**：Q-M/Q-TP/Q-TC、C-NN、repair-log 小节名在四个文件间交叉引用一致（除 A4 映射缺口）。
- **批次/并发/会话复用**：并发上限 3、批次绑定、阶段隔离、R1~R3 同会话规则相互自洽。

---

## 四、建议处理顺序

1. **先修冲突**（一次会话即可全部完成）：C1、C2、C5、C7、C8、C9 是纯文字改动；C3、C4、C6 各需一处规则补充。
2. **再消歧义**：A1~A4 影响判定方向，优先；A5~A10 顺手改。
3. **后做优化**：O11（脚本缓存）独立可先行并用单测回归；O1~O5 提示词精简建议与冲突修复同批改，避免二次触碰同一文件；O9 需你拍板是否放宽「两道澄清不合并」。
