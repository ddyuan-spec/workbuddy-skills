---
name: delivery-suite
description: 交付三件套（推送 / 转 Word / 执行报告）。① push：把 PRD/原型 HTML 通过 gh api PUT 推送到 GitHub Pages 生成短链，覆盖 base64 禁作命令行参数、临时文件禁用 /tmp、404 污染 sha、raw 强制验证四大避坑；② docx：HTML→Word 高保真转换，解决图片缺失（相对路径内嵌 + SVG 光栅化）与标题吞正文/注释泄漏；③ report：本轮改动执行报告（改动清单+验证+推送状态+待办），可直接转发汇报。触发词：推 GitHub、发线上链接、GitHub Pages、短链、上线预览、转Word、导出docx、生成Word版、Word里图不见了、执行报告、改动汇总、这轮改了啥、汇报、本轮总结。
agent_created: true
---

# delivery-suite（交付套件）

**规则本体在 `rules.json`，本文件只是调度壳。执行任何交付动作前必须先读 `rules.json`。**

## 使用方式

1. **读取规则**：`Read {SKILL_DIR}/rules.json`
2. **定位模块**：按用户意图匹配 `modules[].triggers`，锁定 `push` / `docx` / `report` 之一
3. **执行 steps**：按该模块的 `steps` / `usage` 逐步执行
4. **逐条比对 rules**：过滤 `rules[]` 中 `module` 等于当前模块的条目，按 `severity` 处理

## severity 语义

| 级别 | 含义 | 处理 |
|---|---|---|
| `BLOCKER` | 违反即事故 | 禁止交付，必须回头修 |
| `REQUIRED` | 必须执行 | 遗漏须补做后才能交付 |
| `ADVISED` | 建议遵循 | 可按场景裁量 |

## 三个模块速览

| module | 用途 | BLOCKER 数 |
|---|---|---|
| `push` | 推 GitHub Pages 生成短链 | 4 |
| `docx` | HTML → Word 高保真转换 | 3 |
| `report` | 本轮改动执行报告 | 2 |

## 交付前必答

- push：raw.githubusercontent grep 是否命中新内容？（未命中 = 未上线）
- docx：`HEADING HEALTH: suspect=` 是否为 0？
- report：二期待办是否只写进了 PRD §十一？

## 关联

推送前须先过 `prd-suite`（PRD 结构排查）或 `proto-suite`（原型冒烟测试）；全流程编排见 `requirement-workflow`。
