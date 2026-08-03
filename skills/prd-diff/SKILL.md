---
name: prd-diff
description: 定版 PRD（线下 docx）与线上草稿（GitHub Pages HTML）差距对比。提取 docx 文本/大纲，解析 HTML 章节结构，逐项 diff 得出「线上缺哪些章节 / 哪些章节内容单薄 / 哪些需补公式数据演练」，输出结构化差距报告供执行修复。触发词：差距对比、和线下定版比、线上草稿差什么、PRD 比对、定版 vs 线上、diff PRD、对比报告。
agent_created: true
---

# PRD 定版 vs 线上草稿 差距对比（prd-diff）

## 用途
当用户给出**线下定版 PRD（.docx）** 并要求与**线上草稿（GitHub Pages HTML）** 比对差距时使用。产出可执行的差距报告，明确"线上还差什么、要补什么"。

## 环境
- docx 提取用预装 venv：`C:\Users\13364\.workbuddy\binaries\python\envs\docx\Scripts\python.exe`（已装 python-docx / beautifulsoup4 / lxml，无需联网 pip）。
- 注意：Windows 版 python.exe 不接受 `/c/...` 路径，调用时参数用 `C:/Users/...` 正斜杠或 `C:\...` 反斜杠。
- HTML 解析同样用此 venv 的 beautifulsoup4。

## 流程（五步）

### 1. 提取定版 docx 文本 + 大纲
```python
import docx
d = docx.Document(r"C:/梯子/泰小虎优惠券体系重构 需求文档（PRD）v2.0.docx")
lines = []
for p in d.paragraphs:
    s = p.style.name
    if s.startswith("Heading"):
        lvl = s.replace("Heading", "")
        prefix = "#" * int(lvl) + " " if lvl.isdigit() else "# "
        lines.append(prefix + p.text)
    elif p.text.strip():
        lines.append(p.text)
open("_v2_outline.txt", "w", encoding="utf-8").write("\n".join(lines))
```
保留 `_v2_outline.txt`（章节骨架）与 `_v2_full.txt`（全文）供核对。

### 2. 提取线上 HTML 章节结构
用 beautifulsoup4 解析 HTML，抽取所有 `<h1>~<h6>` 标题及对应 id/锚点，形成线上大纲。重点比对：
- 顶层板块（一~九）是否齐全
- 子章节编号（如 §4.3.x / §10.x）是否对齐定版
- 特定章节（如 §4.1.6 数据看板）是否含「计算公式与数据演练」等子项

### 3. 逐项 diff
按章节编号对齐，标记三类：
- 🔴 **缺失**：定版有、线上无（如 §10.7 / §10.8）
- 🟡 **单薄**：线上有标题但内容缺关键子项（如 §4.1.6 仅字段表、缺计算公式与数据演练）
- 🟢 **一致**：结构内容对齐

### 4. 输出差距报告
按 `| 位置 | 状态 | 定版内容 | 线上现状 | 需补动作 |` 表格汇总，并给出**执行清单**（按优先级排序），可直接喂给"改 PRD"动作。

### 5. 修复 + 推送 + 验证
- 用编辑器在线上 HTML 补缺失章节 / 补单薄内容。
- 编号重映射用 Python 正则脚本（如 `4\.3\.(\d)(\.\d+)?` 全局替换），改完**重新 Read 验证未破坏其它引用**再写版本号（避免 "File modified since read" 冲突）。
- 推送用 proto-push skill，raw 验证新内容命中。

## 红线
- ❌ 差距报告里**臆造**定版内容——只比对、不补全；缺失内容由用户确认或标"待确认"。
- ❌ 编号重映射后**不验证引用一致性**就推送（会导致章节锚点/交叉引用断裂）。
- ✅ 章节编号**跳号 / 预留空槽**是有意决策（见 prd-structure-checker §4.34），diff 时不得据此报"缺失"，除非用户明确说漏了一节。
