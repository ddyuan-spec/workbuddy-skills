---
name: batch-annotate
version: 1.0.0
description: 给单文件 HTML 原型批量生成「按钮类 / 字段类」标准化批注，并直接写回原型批注层（proto-annotation 的 __anno_seed）。当用户说「批量批注」「给原型加批注」「按标准格式批注按钮和字段」「给原型写功能说明 / 字段说明」「把功能交互、限制、规则写成批注」时触发。覆盖按钮类（功能说明 / 权限 / 前置条件 / 功能实现 / 文件上传）与字段类（默认数据 / 显示 / 是否支持编辑 / 输入限制 / 选择项 / 选中后展示 / 引用带出 / 计算公式），严格遵循「省略即不写、不冗余、必填必须有、不清楚反问」铁律，sel 用 data-anno 锚点写回 HTML。
type: user
agent_created: true
---

# batch-annotate · 原型批量标准批注

配套 `proto-annotation` 批注层使用：识别原型里的按钮与字段，按统一书写标准生成批注文字，并以 `data-anno` 锚点 + `__anno_seed` 直接写回原型 HTML。评审人本地打开原型即可看到角标，无需口头描述。

## 强制铁律（任何元素适用）
1. **省略即不写**：模板里某条不适用，整条删除；不写空占位、不写「无」、不写「/」。
2. **不冗余**：只写精准内容，不重复标签、不加解释性废话。字段类连【】前的说明文案都不写，只写【】里的准确内容（如写「可编辑」而非「是否支持编辑：该字段支持编辑」）。
3. **必填必须有**：按钮的「功能实现」必填；缺则反问，绝不留空、绝不臆造。
4. **不清楚反问**：权限 / 前置 / 字段来源（引用哪张表、哪个中文名）/ 计算公式 / 选中后展示字段拿不准，先列清单反问用户。
5. **不静默改既有批注**：写回前先读现有 `__anno_seed`，新批注只**追加**（no 续号），不覆盖、不删历史。

## 工作流

### ① 读原型 + 确保批注引擎已注入
- 读目标 HTML。若文件里没有 `__anno_engine`，先注入批注层（幂等，会建空 `__anno_seed`）：
  ```bash
  python ~/.workbuddy/skills/proto-annotation/scripts/inject_anno.py --html <proto.html>
  ```
- 按 `references/element-detection.md` 识别全部可批注元素，分「按钮类 / 字段类」，列成待处理清单。

### ② 逐元素生成批注（严格按 `references/format-spec.md`）
- 按钮类用「**标签 + 冒号 + 内容**」格式（功能说明 / 功能实现 等带标签）。
- 字段类**只写内容、不写标签**（如「可编辑」「默认为空」），每条只占一行，只写适用项。
- 每条只写适用项，不适用整条省略。
- 拿不准的记入 `待反问清单`。

### ③ 反问收口（一次性）
- 把 `待反问清单` 一次性抛给用户（编号列表，或 `AskUserQuestion`）。**拿到答案前不写回**。

### ④ 落锚点（data-anno）
- 对每个批注元素，用 Edit 在原型 HTML 里加 `data-anno="k<序号>"`：
  - 按钮：加在 `<button>` / `<a>` / 触发元素自身。
  - 字段：加在 `.field / .form-item / .row / .item / .col / .cell` 等容器；纯 input 无容器则加在 input 自身。
  - 列表行 / 展示行：加在 `<tr>` / `<li>` / 行容器。
  - 弹窗内字段：加在字段自身；若弹窗容器有 `data-open="openXxx()"` 钩子，定位自动开弹窗。
- 序号全局唯一、连续；同一元素已有 `data-anno` 则**复用**，不新建 key。
- 同一元素需写多条批注：共用一个 `data-anno`，在 seed 里写多条（引擎按锚点合并为橙色计数角标）。

### ⑤ 写回 __anno_seed
- 把批注整理成 `annos.json`：`[{"key":"k1","view":"<视图id或global>","text":"<批注内容>"}]`。
  - `view`：元素所在 `.view / .page` 的 id；无视图切换写 `"global"`（判定法见 element-detection.md）。多视图原型必须填对，否则角标跨视图不显示。
- 跑脚本自动读现有 seed、追加、续号、写回、校验锚点：
  ```bash
  python ~/.workbuddy/skills/batch-annotate/scripts/apply_annos.py --html <proto.html> --annos annos.json
  ```
- 脚本报「锚点缺失」→ 回去补 `data-anno` 再跑。`--force` 可忽略现有 seed 覆盖式写入（默认追加）。

### ⑥ 交付
- 提示用户：本地双击打开原型即可见角标；要上线按 `proto-annotation` 步骤④⑤ 推 GitHub Pages。
- 可选：把 `annos.json` 一并交给用户作为评审底稿。

## 注意
- 角标锚点优先 `data-anno`（引擎 `anchorOf` 规则①），改版不漂；**不要手写冗长 cssPath**。
- 截图仅辅助识别元素；落锚点 / 写 seed 必须基于 HTML 文件。若只给截图没给 HTML，先向用户要 HTML（或产出批注清单让其自行应用）。
- 多命中 / 失联由引擎与 proto-annotation 的「重定位 / 清理失联」兜底，本 skill 只负责生成与写回。
- 写回后建议跑 `proto-annotation` 的 `verify_v4.py` 做一轮回归（角标渲染 + 不穿透）。
