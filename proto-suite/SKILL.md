---
name: proto-suite
description: 原型套件（UX 约束 / 冒烟测试 / 平铺产出）。生成或修改任何前端交互原型（H5/App/小程序/平台端后台/商家端后台）时强制调用。① ux：禁冗余说明文字与小字限制标签、禁 AI 臆造 NEW 角标、有真实截图须 1:1 逐字套用、后台增改查一律独立页禁 Modal、C 端三态拆独立页、重绘掉需求须确认；② smoke：交付前必跑 jsdom 冒烟测试（proto_smoke.js 后台 / proto_smoke_client.js C端），退出码 0 才可交付；③ flat：三种平铺模式（review-board 评审板 / flat-flow 跳转流平铺 / modao 墨刀稿），动手前必须先定 mode。触发词：画原型、改原型、前端原型、后台原型、App原型、小程序原型、冒烟、原型自检、平铺、评审板、墨刀。
agent_created: true
---

# proto-suite（原型套件）

**规则本体在 `rules.json`，本文件只是调度壳。动手画/改任何原型前必须先读 `rules.json`。**

## 使用方式

1. **读取规则**：`Read {SKILL_DIR}/rules.json`
2. **锁定模块**：`ux`（画/改原型）→ `smoke`（交付前门禁）→ `flat`（如需平铺产出）
3. **执行前置动作**：C 端必须先走 `PROTO-STY-002`（AskUserQuestion 确认有无设计稿）；平铺必须先走 `PROTO-FLAT-001`（确定 mode）
4. **逐条比对 rules**：按 `module` 过滤，`BLOCKER` 一票否决
5. **交付前跑 checklist**：先跑 smoke 到退出码 0，再过 `checklist.items` 22 项；有平铺产出的另过 `flat_delivery_checklist` 8 项

## severity 语义

| 级别 | 含义 | 处理 |
|---|---|---|
| `BLOCKER` | 违反即事故 | 禁止交付，必须回头修 |
| `REQUIRED` | 必须执行 | 遗漏须补做后才能交付 |
| `ADVISED` | 建议遵循 | 可按场景裁量 |

## 三个模块

| module | 用途 | 规则前缀 | BLOCKER 数 |
|---|---|---|---|
| `ux` | 交互原型 UX 约束 | `PROTO-TXT` / `PROTO-STY` / `PROTO-STR` | 12 |
| `smoke` | 自动化冒烟测试硬门禁 | `PROTO-SMK` | 1 |
| `flat` | 平铺产出（3 种 mode） | `PROTO-FLAT` | 3 |

## 三条最容易翻车的红线

1. **`PROTO-STR-002`** — `viewXxx` 写在 `</main>` 外 → 跳转空白页。人工 Loop 抓不到，必须靠 smoke 检查项 [A]。
2. **`PROTO-FLAT-001`** — 平铺三种 mode 的卡片规范互斥（review-board 要「查看详情」按钮，flat-flow 明令禁止），不先定 mode 必然出错。
3. **`PROTO-TXT-006`** — AI 自行添加 NEW/HOT/升级 角标属冗余标识，截图有没有都禁止。

## 交付前必答

- smoke 退出码是不是 0？
- `checklist.items` 22 项是否全绿？
- 有 C 端真稿的，金额区/描边/Tab 色值是否与截图一致？
- 有平铺产出的，mode 定了吗？顶部标「无交互」了吗？

## 关联

流程编排见 `requirement-workflow`；PRD 结构排查见 `prd-suite`；推送上线见 `delivery-suite`。
