---
name: pm-master
title: "产品总控（单一入口薄壳）"
description: |
  产品工作总控 / 唯一入口薄壳。当用户不确定该用哪个 skill、或想把多个产品步骤串成一条链路时，由本 skill 分诊并路由到正确的现有 skill（requirement-workflow(lite入口收口壳) / prd-suite / proto-c / proto-admin / proto-design / proto-annotation / batch-annotate / pm-review-board / delivery-suite / coupon-req-flow / coupon-push / coupon-merge-operator / prd-to-dingtalk），多步任务时按「交接摘要」接力。
  触发词：「产品总控」「该用哪个 skill」「帮我推进这个需求」「从头到尾走一遍」「完整链路」「帮我看看走哪个流程」「我有这么个产品问题」「帮我盘一下怎么弄」。
  也适用于：用户描述了一段产品工作（写PRD / 画原型 / 评审 / 推上线 / 优惠券改需求）但没指明调用哪个 skill，或明确说「串起来做」。
  不适用：用户已经点名某个具体 skill（如「用 prd-suite 查结构」），此时直接加载该 skill 即可，不必经本总控。本 skill 自身不产出 PRD / 原型 / 报告内容，只做分诊与编排。
agent_created: true
---

# pm-master · 产品总控（单一入口薄壳）

> **定位**：入口和调度器。你不亲自产出内容，你的工作是：**判断问题类型 → 路由到正确的 skill 或编排一条链路 → 保证上一步的产出能被下一步直接用**。
> 本 skill 是**薄壳**，不含任何流程逻辑本体；所有实质规则都在被路由到的子 skill 里。不要在本 skill 里重写 PRD / 原型 / 评审逻辑。

---

## ⚠️ 唯一入口约定（防坑）

- 本 skill 是产品工作的**唯一总控入口薄壳**。
- `requirement-workflow` 已**降级为 lite 入口收口壳**（只做 intake 提问 + 路由，不持有门禁），不是与本总控平级的另一个总控。用户说「新需求/出PRD/画原型」时，本总控**直接路由到对应能力 skill**（prd-suite / proto-c / proto-admin …），仅在需要先结构化澄清或多能力收口时才经 `requirement-workflow` 做入口；门禁由各能力 skill 自管。
- 原型按端拆分：**`proto-c`**（C端：App/小程序/H5）、**`proto-admin`**（后台：平台端/商家端/运营后台）是两个独立 skill，要求不同，勿混。
- C端原型再拆两形态：**`proto-c`**（带交互原型）与 **`proto-design`**（平铺设计稿 / 无交互 / 可复制源码 / 墨刀）是两个独立 skill，平铺图勿在 proto-c 里画；要带交互原型也勿在 proto-design 里画。
- 其余 `prd-suite` / `proto-c` / `proto-admin` / `delivery-suite` / `coupon-*` / `pm-review-board` 都是**执行流（被路由对象）**，不是总控。
- 编排原则：**一步能解决就一步，不强行套链路**；链路是建议不是流程锁。

---

## 成员名册（执行流）

| Skill | 一句话职责 | 典型输入 → 输出 | 路由时机 |
|---|---|---|---|
| `requirement-workflow` | 需求 lite 入口收口壳（intake 提问 + 路由，无门禁） | 模糊需求 → 澄清后路由到能力 skill | 「新需求但信息不全」「先理清再动手」「需求收口」（可选入口，非必经） |
| `prd-suite` | PRD 域内调度壳 | 写/审 PRD → 结构校验/单页§四/定版对比/截图重截 | PRD 写改审、结构排查、单页详情、定版 vs 线上、截图过期 |
| `proto-c` | C端交互原型（App/小程序/H5：ux/smoke/shot，知识库 UI 索引先行+交互冒烟） | C端交互原型需求 → 合规可交互原型+冒烟通过 | 画/改 C端（App/小程序/H5）带交互原型、冒烟、三态拆独立页 |
| `proto-admin` | 后台原型（平台端/商家端/运营后台：ux/smoke/shot，增改查独立页禁Modal） | 后台原型需求 → 合规原型+冒烟通过 | 画/改后台/管理端原型、冒烟、逐页确认 |
| `proto-design` | C端平铺设计稿（无交互/可复制源码/墨刀：ux/flat，知识库 UI 索引先行+FLAT 模块） | C端平铺稿需求 → 合规平铺图+flat_delivery_checklist | 平铺图/墨刀稿/可复制源码/评审板/跳转流平铺 |
| `pm-review-board` | 六角色模拟评审（产品/研发/测试/设计/运营/法务） | PRD/原型 → 分级问题清单+通过/不通过 | 「评审」「过会」「review」「查漏补缺」 |
| `delivery-suite` | 交付三件套（push/docx/report） | HTML → GitHub短链/Word/执行报告 | 推GitHub、转Word、出执行报告、要上线预览 |
| `coupon-req-flow` | 优惠券增量需求工作流（隔离→确认→合并→登记待推） | 优惠券小改动 → 本地合并就绪+入推送队列 | 优惠券改动、coupon-platform/prd.html、红黑规则、tasks 隔离 |
| `coupon-push` | 优惠券独立推送（队列驱动） | push-queue.json(MERGED_READY) → 线上发布+健康检查 | 优惠券正式发布上线（用户另开任务执行） |
| `coupon-merge-operator` | 优惠券合并操作员角色 | 已确认草稿 → 合入正式文件（只合并不撰写） | 多任务并行合并、需专人把关合并 |
| `prd-to-dingtalk` | PRD → 钉钉文档推送（三模式：A 图片增量 / B 块级增量 / **C 纯文字零图传**） | 本地 HTML/MD PRD → 钉钉在线文档（HTML→MD 清洗 / 图片内部化 / 增量同步 / 回读验证） | 「推钉钉」「发钉钉文档」「PRD 发钉钉」「同步到钉钉」「改钉钉文字」 |
| `proto-annotation` | 原型批注层引擎（注入/渲染/顶层弹窗隔离/失联重定位/推 GitHub） | 单文件 HTML 原型 → 可本地批注 + 角标 + 同步 GitHub Pages | 给原型装批注能力、评审批注管理、批注同步上线 |
| `batch-annotate` | 批量标准批注生成器（按钮/字段类标准化批注写回 seed） | 已注入引擎的原型 → 带标准化批注角标的原型 | 「批量批注」「给原型加批注」「写功能/字段说明」 |

---

## 第一步：问题分诊

收到请求后，先分诊到三类之一：

1. **判断类**（该不该做、真伪需求、值不值、怎么取舍）→ 见下方「覆盖缺口」，目前无专门顾问团 skill，转为建议 + 路由到 `prd-suite` 阶段零需求体检或 `pm-review-board`。
2. **产出类**（写文档、排序、出原型、做评审、推上线）→ 按下方单点路由表选 1 个执行流。
3. **链路类**（「从想法推进到上线」「完整走一遍」「串起来」）→ 按预置链路编排。

分不清判断类还是产出类时，用这个测试：**用户要的是「一个结论/视角」还是「一份可交付物」？** 前者判断类，后者产出类；既要结论又要交付物 → 链路类（先判断后产出）。

---

## 第二步：单点路由表

| 用户在说什么 | 路由到 | 备注 |
|---|---|---|
| 新需求 / 出 PRD / 梳理需求（信息已齐，直接产出） | `prd-suite` | 按产出类型直接路由到能力 skill，门禁由该 skill 自管 |
| 画/改 C端带交互原型（App/小程序/H5） | `proto-c` | 含知识库 UI 索引先行 + 交互冒烟门禁；三态拆独立页 |
| C端平铺图/墨刀稿/可复制源码/评审板/跳转流平铺 | `proto-design` | 无交互、走 FLAT 模块 + flat_delivery_checklist；先定 mode（review-board/flat-flow/modao） |
| 画/改后台原型（平台端/商家端/运营后台） | `proto-admin` | 含增改查独立页禁 Modal + 截图逐字 + 冒烟门禁 |
| 新需求但信息不全 / 要先理清范围再动手 | `requirement-workflow` | lite 入口收口壳做 intake 澄清后路由 |
| 写/改/审 PRD、结构排查、单页§四、定版对比、截图重截 | `prd-suite` | 按意图命中 structure/detail/diff/screenshot 模块 |
| 帮我评审 / 过会 / review / 查漏补缺 | `pm-review-board` | 可接收 PRD 或原型 |
| 推 GitHub / 转 Word / 出执行报告 / 上线预览 | `delivery-suite` | 推前须先过 prd-suite / proto-c / proto-admin / proto-design 门禁 |
| 推钉钉 / 发钉钉文档 / PRD 同步到钉钉 / 同步 PRD 到钉钉（**含图或首次**） | `prd-to-dingtalk` 模式 A 增量 | 与 delivery-suite 的 GitHub Pages 推送互不冲突：钉钉走 dws CLI，GitHub 短链走 gh api；推前须先过 prd-suite / proto-c / proto-admin 门禁；只传变化图，不重传全量 |
| **改钉钉文字 / 钉钉改一段 / 改错别字改表格 / 钉钉小改** | `prd-to-dingtalk` **模式 C 纯文字** | 前置：改动**须先落 GitHub**（未推则先走 delivery-suite + 回读 size 一致）。再 `--dry-run` 确认 NEW+CHANGED=0 → `--apply` 不传任何图 → `--finalize` → 一次 `overwrite`。秒级完成，**不要走全量重推，也不要绕开 GitHub 直接手改钉钉** |
| 三端对版本 / 钉钉同步了没 / 本地草稿领先没 / 有没有没推的 | `prd-sync` | 只管版本账本（manifest / status / record），**不负责推送**；推送归 prd-to-dingtalk |
| 优惠券小改动 / coupon-platform/prd.html / 红黑规则 | `coupon-req-flow` | 隔离→确认→合并→登记待推 |
| 优惠券正式发布上线 | `coupon-push` | 消费 push-queue.json，队列驱动 |
| 多任务并行合并、要专人把关 | `coupon-merge-operator` | 只合并已确认草稿 |
| 给原型批量加批注 / 写功能说明 / 写字段说明 / 批注按钮和字段 | `batch-annotate` | 内部依赖 proto-annotation 引擎；原型未注入引擎则先注入再批量写；口径不明处按铁律反问，绝不臆造 |
| 给原型注入批注层 / 评审批注管理 / 批注同步 GitHub Pages | `proto-annotation` | 批注系统底座；batch-annotate 在其之上工作，单独用也可做本地评审批注 |

路由后：说明选择理由（一句话），确认后加载对应 skill 执行。用户明显着急或指令明确时直接执行，不要多问。

---

## 第三步：预置链路

用户的任务横跨多步时，推荐链路并列出每步的交接物。**每一步的产出必须是下一步的合法输入**——这是链路编排的唯一硬规则。

### 链路 A：需求输出（最常用，本总控直接编排，不依赖 requirement-workflow 内部步骤）
```
[新需求描述]
 →（可选）requirement-workflow 做 intake 澄清
 → proto-c / proto-admin（画带交互原型，各自自管门禁 + 冒烟）｜要平铺稿走 proto-design
 → prd-suite（写 PRD，自管 PRD 权威索引先行 + 结构排查）
 → pm-review-board（评审，按需）
 → delivery-suite（推送 GitHub Pages / 转 Word / 执行报告，按需）
```
> 单点说「新需求/出PRD」即按产出类型直接路由对应能力 skill；多步才走完整链路，链路由本总控编排而非某子 skill 内部串。

### 链路 B：PRD → 评审 → 修订
```
[写/改 PRD] → prd-suite（structure/detail 产出 PRD + 待确认项清单）
 → pm-review-board（输入 PRD，输出分级问题清单 + 通过/不通过）
 → prd-suite 修订（输入问题清单，输出修订版 PRD）
 → delivery-suite（转 Word / 推线上，按需）
```

### 链路 C：优惠券增量
```
[优惠券小改动] → coupon-req-flow（隔离草稿 → 澄清盘问 → 出原型 → 写 PRD 草稿 → 用户确认 → 合并转黑 → 登记待推）
 → coupon-merge-operator（多任务时专人合并把关，按需）
 → coupon-push（用户另开任务，消费队列推送上线）
```

### 链路 D：原型 → 评审 → 交付
```
[画/改原型] → proto-c / proto-admin（ux + smoke 冒烟门禁，带交互原型）；平铺图走 proto-design（FLAT 模块 + flat_delivery_checklist）
 →（可选）proto-annotation（注入批注层）+ batch-annotate（批量加标准化批注 / 评审人本地批注）
 → pm-review-board（输入原型，输出评审结论）
 → delivery-suite（推 GitHub Pages / 转 Word，按需；批注已内嵌 __anno_seed 一并推送）
```

### 链路执行规则
1. **开始前报价**：列出计划链路、每步产出物、预计需要用户参与的确认点，让用户砍步骤。
2. **步间交接**：每步结束输出一段「交接摘要」（≤10 行：本步结论 + 下步需要的输入），而不是让下一步重读全文。
3. **可中途退出**：每步完成即是独立可用的交付物，用户随时可以停。
4. **不强推链路**：用户只要一步就给一步。

---

## 交接摘要规范（链路模式必做）

每个执行流完成后，本总控（或执行流自身）输出一段「交接摘要」，供下一个 skill 直接使用：

```markdown
## 交接摘要（<上一步 skill 名 → 下一步 skill 名>）
- 本步结论：<一句话说清产出了什么、关键决策/待确认项>
- 交付物位置：<文件路径 / 短链 / 队列状态>
- 下一步所需输入：<下一个 skill 直接要用的内容，避免重读全文>
- 遗留风险：<未闭环的待确认项 / 需在下一步处理的点>
```
篇幅 ≤10 行。

---

## 澄清规则

- 最多一轮澄清，问题不超过 4 个，按「阻塞路由的 → 影响质量的」排序。
- 用户给的信息足够路由时，不澄清，直接路由（缺的信息留给目标 skill 自己问）。

---

## 覆盖缺口（暂未覆盖，不硬编）

参考 pm-master 的完整体覆盖，以下能力**我们当前没有对应 skill**，遇到时**明确告知用户「暂未覆盖」**，不要硬套现有 skill 冒充：

| 缺失能力 | 参考名 | 遇到时的处理 |
|---|---|---|
| 数据分析 / 指标归因 | pm-analytics | 说明暂未覆盖；如需可后续新增 |
| A/B 实验设计 | pm-experiment-designer | 说明暂未覆盖 |
| 需求优先级排序 | pm-prioritization-engine | 说明暂未覆盖 |
| 竞品拆解 | pm-competitor-deconstructor | 说明暂未覆盖 |
| 复盘报告 | pm-postmortem-writer | 说明暂未覆盖 |
| 专家顾问团（判断类） | pm-advisory-* | 说明暂未覆盖；判断类问题先转 prd-suite 阶段零需求体检或 pm-review-board |

---

## 降级与诚实边界

- **目标 skill 未安装**：按名册中的「一句话职责」做低保真版本，并提示安装完整 skill。
- **超出覆盖范围**：直说不在覆盖范围内，不硬套。
- **链路 ≠ 必然更好**：简单任务走链路是浪费，一步能解决就一步。
- 本总控只保证「路由对 + 链路通」，各 skill 的产出质量由各自的检查清单负责。
