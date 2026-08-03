---
name: prd-suite
description: "PRD / 需求文档总控 suite（合并 prd-structure-checker + prd-diff + prd-single-page-detail + prd-screenshot-sync）。当用户产出、审阅、修订「需求文档 / PRD / 产品需求说明书 / 功能需求文档」，或要做定版docx vs 线上HTML差距对比、单页§四需求详情、原型截图对齐重截时触发。规则本体在 rules.json（4 modules：structure 结构排查+check_prd.py / detail 单页§四模板 / diff 定版vs线上 / screenshot 截图重截），加载器只读本文件 frontmatter 做触发匹配，真正规则必须读 rules.json。触发词：PRD、需求文档、产品需求、功能需求、需求评审、终稿、排查结构、写PRD、差距对比、定版vs线上、单页需求详情、截图过期、重截PRD图。"
agent_created: true
---

# PRD 总控 Suite（prd-suite）

> **壳 + 芯结构**：本文件是**调度壳**，加载器只扫描这里的 frontmatter 做触发匹配。
> 全部规则在 `rules.json`（4 个 module、55 条规则、22 项交付前自检 checklist）。
> **动手前先 `Read` 完整读取 `rules.json`**，再按命中的 module 过滤规则执行；禁止凭记忆套用旧 skill 的散文规则。

## 何时触发

| 用户意图 | 命中 module | 动作 |
|---|---|---|
| 写 / 改 / 审 PRD、结构排查、终稿 | `structure` | 读 `rules.json` 的 `structure` 模块 + 跑 `scripts/check_prd.py` |
| 单页 §四 需求详情、基于原型写某页 PRD | `detail` | 读 `rules.json` 的 `detail` 模块 + 套 `references/prd-detail-template.md` |
| 定版 docx vs 线上 HTML 差距对比 | `diff` | 读 `rules.json` 的 `diff` 模块 + 五步流程 |
| 原型改版致 PRD 截图过期、重截 | `screenshot` | 读 `rules.json` 的 `screenshot` 模块 + 跑 `scripts/recap_shots.py` |

## 执行约定

1. **先读规则本体**：`Read` 本目录 `rules.json`，确认 `severity_semantics` 三档（BLOCKER 禁止交付 / REQUIRED 必须补做 / ADVISED 可裁量）。
2. **按 module 过滤**：只执行与当前意图相关的 module 规则；跨 module 任务（如写 PRD 同时引用原型截图）须同时加载 `structure` + `screenshot`。
3. **跑确定性扫描**：structure 模块用 `scripts/check_prd.py <prd.html>`（支持 `.md/.txt/.docx/.html`，阶段1~4；`--strict` 阻断模式；`--auto-fill` 自动补图）；把脚本输出作为初判，再结合 `checklist` 做人工核对。
4. **待确认项不可臆造**：凡不确定数据，二选一——「⚠️ 待确认 @干系人」占位 或 `AskUserQuestion` 反问；写完汇总 N 处待确认项。
5. **定稿门槛**：所有 BLOCKER 通过（或用户明确豁免）才允许定稿 / 进入评审。

## 附属文件

- `rules.json`：规则本体（4 module + checklist）。
- `scripts/check_prd.py`：结构扫描脚本（阶段1~4 + §四 深度 + 自动补图），来自 prd-structure-checker。
- `scripts/recap_shots.py`：原型截图过期重截脚本，来自 prd-screenshot-sync。
- `references/prd-structure.md`：一~九 必含板块权威清单（对齐桌面 260715 docx）。
- `references/prd-detail-template.md`：§四 逐页面 2.1~2.7 书写范本。
- `references/prd-authoring-skeleton.md`：写作骨架（一~九 + §四 每页空壳）。
- `references/tracking-spec.md`：《泰小虎埋点规范 v2.3》结构化参考。
- `references/checklist.md`：单页 §四 自检清单。

## 严重度语义

- 🔴 **BLOCKER**：违反即事故，禁止交付，必须回头修。
- 🟡 **REQUIRED**：必须执行，遗漏须补做后才能交付。
- 🟢 **ADVISED**：建议遵循，可按场景裁量。
