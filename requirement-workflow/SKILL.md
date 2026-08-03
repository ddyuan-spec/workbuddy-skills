---
name: requirement-workflow
description: "需求输出【强制】workflow 总控 suite（合并 requirement-workflow + 吸收 agent-era-delivery 为 lite 模式）。当用户说「新需求/出PRD/画原型/梳理需求」或要「Agent时代三件套交付(proposal.md+原型.html+spec.md)」时触发。规则本体在 rules.json（2 modules：flow 10步主流程+门禁 / lite 三件套轻量模式），加载器只读本文件 frontmatter 做触发匹配，真正规则必须读 rules.json。触发词：新需求、出PRD、画原型、梳理需求、需求三件套、Agent时代交付、proposal.md、spec.md、评审原型页。"
agent_created: true
---

# 需求输出 Workflow 总控 Suite（requirement-workflow）

> **壳 + 芯结构**：本文件是**调度壳**，加载器只扫描这里的 frontmatter 做触发匹配。
> 全部强制门禁与约束在 `rules.json`（2 module、26 条规则、`workflow_steps` 10 步概览、`gates` 门禁定义）。
> **动手前先 `Read` 完整读取 `rules.json`**，按命中 module（flow / lite）过滤规则执行；禁止凭记忆套用旧散文。

## 何时触发

| 用户意图 | 命中 module | 动作 |
|---|---|---|
| 新需求 / 出 PRD / 画原型 / 梳理需求 | `flow` | 走 10 步主流程，过 `gates` 门禁 |
| 三件套 / Agent 时代交付 / proposal.md+原型.html+spec.md | `lite` | 走三件套轻量模式（不拦截 flow 触发词） |

## 执行约定

1. **先读规则本体**：`Read` 本目录 `rules.json`，确认 `severity_semantics` 三档（BLOCKER 禁止进入下一步 / REQUIRED 须补做 / ADVISED 可裁量）。
2. **按 module 过滤**：只执行与意图相关的 module 规则；小修小补可裁剪步骤，但 `scope-gate`（REQ-FLOW-002）与 `produce-hook`（REQ-FLOW-011）仍生效。
3. **门禁串联**：`gates` 定义了三道硬门禁——范围确认门禁（Step1→2）、产出校验 Hook（每步产出后）、PRD 结构门禁（Step4）。任一不通过不得继续。
4. **禁止臆测**：不确定数据二选一——「⚠️ 待确认 @干系人」占位 或 `AskUserQuestion` 反问。
5. **下游 suite 联动**：flow Step3 原型过 `proto-suite`；Step4 PRD 过 `prd-suite`；Step7/8 推送与转 Word 用 `delivery-suite`。

## 10 步流程概览（详见 rules.json `workflow_steps`）

```
Step 0  任务判断与准备
Step 1  收集项目信息 → 功能现状澄清(1.4) → 功能生命周期映射表初稿(1.5) → 分端口现状调研四象限(1.6)
【范围确认门禁】用户逐行标注确认本期范围 → 才进 Step 2
Step 2  需求梳理 → 统一 HTML 图集（严格基于已确认范围）
Step 3  输出可交互原型（每端口）+ 客户端设计原型平铺稿（墨刀用）
Step 4  PRD 结构检查（过 prd-suite structure）
Step 5  PRD 输出（Word）+ 待确认项文档 + 反问 Loop
Step 6  本地路径确认
Step 7  终版存档 GitHub（推送后远端门禁）
Step 8  评审后本地修改 → 再推送
Step 9  收尾：归档、删过程文件、更新索引与记忆
```

## 三道硬门禁（详见 rules.json `gates`）

- **scope-gate**（REQ-FLOW-002）：Step1→Step2 之间，功能生命周期映射表未逐行标注确认前，AI 不得生成图集/FR。
- **produce-hook**（REQ-FLOW-011）：Step 2/3/4/5/6/7/8 产出后必过通用三查（数量/格式/内容错乱），Step7/8 推送后查远端 404 + 预览页。
- **prd-gate**（REQ-FLOW-008）：Step4 PRD 必须过 prd-suite structure 模块 check_prd.py 输出「通过」。

## 附属文件

- `rules.json`：规则本体（2 module + gates + workflow_steps）。
- `references/produce-check-hook.py`：每步产出校验脚本（`--step N --expect 文件名...` / `--scope` 范围门禁机器校验）。
- `references/requirement-workflow-reference.md`：详细参考手册（10 步逐项说明、四象限框架、文件命名规范、图片校验 Loop 详解）。

## 严重度语义

- 🔴 **BLOCKER**：违反即事故，禁止进入下一步/交付，必须回头修。
- 🟡 **REQUIRED**：必须执行，遗漏须补做后才能交付。
- 🟢 **ADVISED**：建议遵循，可按场景裁量。
