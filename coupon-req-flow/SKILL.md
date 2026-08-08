---
name: coupon-req-flow
description: 泰小虎优惠券增量需求迭代工作流（仅优惠券需求）。当用户提交一个优惠券小需求改动、要「先出独立原型→确认→合并」，或提到 coupon-platform.html / coupon-prd.html / tasks 隔离 / 红黑规则 / 截图替换时调用。强制读取 coupon-spec.md 作为契约，先 fork 本地隔离草稿（不入库），原型只改需改字段、PRD 仅新需求标红，过 prd-suite/proto-suite 门禁，用户确认后合并转黑并推送 GitHub Pages。
---

# coupon-req-flow · 泰小虎优惠券增量需求工作流

> 本 skill 实现《优惠券需求迭代规范》（`核心业务/优惠券/coupon-spec.md`）。两者必须保持一致；改其一同步改另一。

## 何时用

- 用户提交**一个优惠券小需求改动**，要「先出原型给你确认，确认了再合并」。
- 用户提到：平台端正式原型 `coupon-platform.html`、正式 PRD `coupon-prd.html`、本地 `tasks/` 隔离、红黑规则、截图重截替换。
- 多任务并行做优惠券需求时，统一按本流程隔离与串行合并。

**不适用**：非优惠券需求、C 端页面（App/H5/小程序）独立生成（走前端样式共识另定流程）、一次性大版本重做（走 requirement-workflow）。

## 强制前置：读契约与事实

1. 读 `核心业务/优惠券/coupon-spec.md`（本流程的全部规则、URL、端口范围、红黑规则、合并协议）。
2. 读**两个正式文档**取「当前事实」（禁止凭空假设）：
   - 正式原型：https://ddyuan-spec.github.io/taixiaohu/coupon-platform.html （本地源 `核心业务/优惠券/平台端后台原型.html`）
   - 正式 PRD：https://ddyuan-spec.github.io/taixiaohu/coupon-prd.html （本地源 `核心业务/优惠券/优惠券体系新需求PRD.html`）
3. 若需求涉及 C 端页面，另读样式共识：仓库 `docs/泰小虎_前端原型设计.md`（在线 `…/docs/泰小虎_前端原型设计.html` v1.2）。

## 工作流（严格顺序）

### 步骤 1 · 开隔离草稿（不入库）
- 建 `核心业务/优惠券/tasks/{task-id}/`，`{task-id}` 用语义短名（如 `2026-08-07-share-threshold`）。
- 复制正式原型为 `tasks/{task-id}/coupon-platform.html`（完整副本）。
- 本任务 PRD 草稿：`tasks/{task-id}/prd-draft.html`（或 `.md`）。
- **不推 GitHub Pages、不进仓库。**

### 步骤 2 · 写 SCOPE.md（范围声明）
在 `tasks/{task-id}/SCOPE.md` 写清影响范围：
- PRD：章节（如 §10.3）、字段名；
- 原型：视图（`go('sendEdit')` 等）、组件 / 字段。
用于后续串行合并时查重叠。

### 步骤 3 · 出独立原型（只改需改字段）
- 在 `tasks/{task-id}/coupon-platform.html` 上**只改本任务需要的视图 / 字段**，其余样式 / 字段原样保留（干净一致）。
- 遵守 proto-suite UX 约束：禁冗余说明小字、禁 AI 臆造 NEW 角标；有真实截图须 1:1 逐字套用；后台增改查独立页禁 Modal。
- 若涉及截图但与说明 / 原型不符：用 Playwright（本机 chromium-1234）按最新原型重截，并在独立阶段加红字说明「📌 本截图已于 YYYY-MM-DD 替换：…已按最新原型重新截取」（color:#d32f2f）。

### 步骤 4 · 写 PRD 草稿（仅新需求标红）
- 在 `tasks/{task-id}/prd-draft.html` 写本任务需求，**仅新需求相关文字标红 `color:#d32f2f`**，既有正文 / 历史说明 / 元注释一律黑 `color:#000000`。
- 过 `prd-suite` / `prd-structure-checker` 结构校验：一~九板块齐全、红线词 0、待确认悬空 0（待确认项用「⚠️ 待确认 @干系人」占位，不阻断草稿，但合并前必须清零）。

### 步骤 5 · 交付确认（不动正式文档）
- 把 `tasks/{task-id}/` 下的原型 + PRD 草稿呈现给用户确认。
- **此阶段绝不改线上正式文档。** 等用户明确「确认 / 可以合并」再进步骤 6。

### 步骤 6 · 串行合并（检查重叠）
- 合并前检查本任务 SCOPE 与「已合并任务」「在途任务」是否重叠；**重叠则停下，问用户确认**再继续。
- 同一时间只合并一个任务。

### 步骤 6.5 · 合并前预改动（重复检测）⚠️ 必跑
合并到正式文件**之前**必须做一次「预改动」扫描，落实「只改你改过的部分、别人已改过的绝不重复改」：
1. **基线 diff**：对正式源文件（平台端后台原型.html / 优惠券体系新需求PRD.html）与 `tasks/{task-id}/` 下的草稿做 diff（Python `difflib` 或 `git diff --no-index`），导出本任务精确改动集（改动块清单 + 目标标记列表）。
2. **重复检测（核心）**：逐个核对改动点在正式文件中的**当前状态**——
   - 目标标记（如「已领取」列、弹窗 id、`cpTotal` 输入、字段行等）**已不存在** → 说明被其他已完成任务提前改过，**该处跳过、不重复改**，并在 SCOPE / 任务日志标注「已存在，跳过」；
   - 目标标记**仍存在** → 本任务正常应用该改动。
3. **无意外差异校验**：确认正式文件相对「草稿复制时的基线」仅多出本任务改动，无其他并行任务造成的意外漂移；若有意外差异，停下问用户确认。
4. **合并 + 二次校验**：确认无重复后，将草稿合入正式文件；合并后**再次 diff** 验证：正式文件与定稿草稿差异块数 = 0（证明只落了本任务改动、零额外变更）。
> 本步骤是防重复劳动 + 防覆盖他人成果的硬性保障，**每次合并必跑**，不可省略。

### 步骤 7 · 合并转黑 + 推送
- 原型改动合回正式原型源文件（`核心业务/优惠券/平台端后台原型.html`），保持其余样式不变。
- PRD 改动合回正式 PRD 源文件（`核心业务/优惠券/优惠券体系新需求PRD.html`），**整篇转黑**（含本任务新需求文字，最终 `color:#d32f2f` 计数应为 0）。
- 推送 GitHub Pages（gh api PUT，详见 delivery-suite / 用户记忆的 GitHub Pages 推送四避坑）：
  - 用 `--input body.json`，base64 不作命令行参数；临时文件放当前工作目录（禁 `/tmp`）；404 污染 sha 用退出码判断；命令前加 `HTTPS_PROXY=""`。
- 回读线上验证：PRD `color:#d32f2f` = 0、新内容已落地。

### 步骤 8 · 收尾
- 删除 `tasks/{task-id}/` 目录（Python `os.remove` 绝对路径，因 shell `rm` 被 safe-delete 拦截）。
- 如文档升版，更新 `coupon-spec.md` §7 基线版本。
- 向 `核心业务/优惠券/.workbuddy/memory/YYYY-MM-DD.md` 追加本次任务记录。

## 关键不变量（红线）
- 官方文档（线上 `coupon-platform.html` / `coupon-prd.html`）**永远全黑**，无红字残留。
- 原型**只改需改字段**，其余样式 / 字段不变。
- 隔离草稿**不入库不推线上**，合并完即清。
- 合并前必跑「预改动 / 重复检测」（步骤 6.5），确认无重复改动再合入。

## 复用现有 skill
- PRD 结构校验：`prd-suite`（含 `prd-structure-checker`）。
- 原型 UX / 冒烟：`proto-suite`。
- 推送 GitHub Pages：`delivery-suite`。
- 大版本 / 新需求立项：`requirement-workflow`（本流程是其轻量增量子集）。
