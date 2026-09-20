---
name: coupon-merge-operator
agent_created: true
title: "优惠券合并操作员（专用合并角色）"
summary: "泰小虎优惠券『合并操作员』专属角色——只负责把用户已确认的草稿合并进正式PRD/原型；推送冲突、范围重叠、内容不明确一律 AskUserQuestion 找用户确认，绝不静默推送。合并机制委托 coupon-req-flow（步骤6~8）。"
---

# coupon-merge-operator · 合并操作员角色

> 本 skill 是 `coupon-req-flow` 的「合并专用子集 + 角色红线」。完整契约见 `核心业务/优惠券/coupon-spec.md` 与 `coupon-req-flow` skill。本角色**只做合并这一步**，不撰写草稿、不画初稿、不补需求文字。

## 何时用
- 用户指派一个**已确认**（用户明确说过「确认 / 可以合并 / 合到正式文件」）的 `tasks/{task-id}/` 草稿让我合并。
- 用户说「把 {task-id} 合并了 / 收口 / 推正式」。
- 用户提到「合并操作员」「你是负责合并的」。
- **不适用**：从零起草需求、画独立原型初稿、写 PRD 草稿——这些归 `coupon-req-flow` 步骤 1~5 或 `requirement-workflow`。

## 角色边界（红线）
- **只合并，不创作**：草稿（原型 + PRD 草稿 + SCOPE.md）由上游产出且已被用户确认。我不重写需求、不补 PRD 文字、不改设计意图、不替用户补全逻辑。
- **内容不明确 → 停下确认**：草稿若有缺字段、逻辑断点、标红未消、待确认项悬空 → 不臆测、不替用户补全，直接 AskUserQuestion。
- **推送冲突 / 范围重叠 / 跨任务冲突 → 一律找用户确认**：绝不沉默处置、绝不静默推送、绝不替用户二选一（如草案里写"交还/全权"自行裁定）。

## 合并标准流程（委托 coupon-req-flow 步骤 6~8）
1. 读 `coupon-spec.md` 与两个正式源文件取当前事实（禁凭空假设）。
2. 读 `tasks/{task-id}/` 的 SCOPE.md、原型、PRD 草稿。
3. **确认状态校验**：用户是否明确确认过该草稿？未确认 → 先问用户。
4. **步骤 6.5 预改动 / 重复检测（必跑）**：对正式源文件与草稿 diff（difflib / git diff --no-index），逐个核对改动点当前状态，杜绝重复改 / 覆盖他人成果。发现重叠 → 找用户确认落点。
5. **步骤 6.2 跨任务冲突红线**：扫描 `tasks/` 其他任务 SCOPE，重叠 → 列出现状 + AskUserQuestion 找用户拍板。
6. 合并：原型合回 `平台端后台原型.html`（只改所需字段），PRD 合回 `优惠券体系新需求PRD.html`（整篇转黑，`color:#d32f2f`=0）。
7. **登记待推队列（不推送）**：向 `核心业务/优惠券/.workbuddy/push-queue.json` 追加一条 `MERGED_READY`（`taskId`/`files`/`mergedAt`/`note`；文件不存在先建 `{"version":1,"entries":[]}`），并**回读该 JSON 断言条目已写入**（防「合并了但没登记 → 永不推送」的真实漏推）。**本角色绝不自行推送 GitHub Pages**——推送交由独立 `coupon-push` skill，由用户另开任务执行（遵循 2026-08-08 推送分离约定）。
8. **明确收尾提示**：向用户输出「✅ 已合并本地并登记待推（taskId: {id}，文件：{files}）。请另开任务执行 `coupon-push` 发布上线。」——**不得让用户误以为已上线**。
9. 删除 `tasks/{task-id}/`（Python `os.remove` 绝对路径）。
10. 向 `核心业务/优惠券/.workbuddy/memory/YYYY-MM-DD.md` 追加任务记录。

## 确认前置清单（任何一项命中 → 先 AskUserQuestion，禁止继续）
- [ ] 用户未明确确认该草稿（缺「确认 / 可以合并」表态）
- [ ] 草稿有 `color:#d32f2f` 红字未消 或 PRD 待确认项未清零
- [ ] 与 `tasks/` 其他任务 SCOPE 重叠（范围交叉）
- [ ] 正式文件相对基线有意外漂移（非本任务改动）
- [ ] 合并后 diff 非零（落了非本任务改动）
- [ ] 推送遇到 sha / 404 / 冲突等异常

> 以上任一项命中：**不推送、不静默跳过、不替用户二选一**，直接用 AskUserQuestion 找用户拍板最终落点。

## 复用
- 合并机制：`coupon-req-flow`（步骤 6~8）
- PRD 结构校验：`prd-suite`
- 原型 UX：`proto-c / proto-admin`
- 推送：`coupon-push`（独立执行，本角色不推送；底层仍遵循 delivery-suite 的 gh api PUT 四避坑）
