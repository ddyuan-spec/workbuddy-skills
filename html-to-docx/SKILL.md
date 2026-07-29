---
name: html-to-docx
description: "HTML → Word(.docx) 高保真转换器。当用户要把 PRD / 需求文档 / 原型 / 图集等 HTML 产出为可编辑 Word 文档时使用。重点解决两类反复出现的「Word 图片缺失」根因：① 相对路径 <img src='xxx.png'> —— 改为读取本地字节内嵌（不依赖外部文件）；② 内联 <svg> 矢量图 —— Word 不支持 SVG，先用 msedge headless 光栅化为 PNG 再内嵌。同时保留标题层级、表格边框(Table Grid + 显式边框)、列表、加粗、链接、颜色与中文(eastAsia 字体)。触发词：转Word、导出docx、HTML转文档、生成Word版、图片缺失、Word里图不见了。"
agent_created: true
---

# HTML → Word 转换器（html-to-docx）

## 用途

把一份结构良好的 HTML（PRD / 需求文档 / 原型页 / 图集）转成**高保真、可编辑**的 `.docx`。
最大卖点：彻底规避「Word 里图片全是空白/缺失」这个反复踩的坑。

### 为什么图片会缺失（历史根因）

1. **相对路径图片**：HTML 里 `<img src="assets/xxx.png">`，普通转换工具不会把图片字节塞进 docx，只留一个外部链接 → 在别的机器/离线打开就丢了。
   → 本 skill 改为 `open(path,'rb')` 读字节，用 `run.add_picture(BytesIO(data))` **内嵌**进 docx 的 media 区。
2. **内联 SVG 矢量图**：PRD 里的流程图常是 `<svg>` 画的。Word **不支持渲染 SVG** → 直接丢图。
   → 本 skill 先用 `msedge --headless=new --screenshot` 把每个 `<svg>` 光栅化成 PNG（2x 清晰度），再像普通图片一样内嵌。

## 何时使用

- 用户说「转成 Word」「导出 docx」「给我文档 word」「HTML 转文档」。
- 任何 HTML 交付物需要 Word 版的场景（PRD 终稿、需求梳理、原型说明）。
- 之前用别的办法转出 Word 后图片丢了 → 用本 skill 重转。

## 环境与依赖

- **专用 venv（已预装 python-docx / beautifulsoup4 / lxml / PIL，无需联网 pip）**：
  `C:/Users/13364/.workbuddy/binaries/python/envs/docx/Scripts/python.exe`
- **msedge（用于 SVG 光栅化）**：自动探测 `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe` 或 `C:/Program Files/Microsoft/Edge/Application/msedge.exe`。

## 用法

```bash
C:/Users/13364/.workbuddy/binaries/python/envs/docx/Scripts/python.exe \
  C:/Users/13364/.workbuddy/skills/html-to-docx/scripts/html_to_docx.py \
  <input.html> <output.docx> [--edge <msedge.exe>]
```

## 实现要点（scripts/html_to_docx.py）

- 用 BeautifulSoup 解析，按文档顺序递归遍历 `body` 子节点。
- 标签映射：`h1→Title` / `h2→Heading1` / `h3→Heading2` / `h4→Heading3` / `h5→Heading4`；`p→段落`；`ul/ol→项目符号/编号列表`；`table→docx 表格(显式边框)`；`b/strong→加粗`；`a→超链接`；`code→等宽红字`。
- **中文**：给 Normal 与各级 Heading 设 `w:rFonts` 的 `ascii/hAnsi/eastAsia` 为 `Microsoft YaHei`，防止中文变方框。
- **表格边框**：除引用 `Table Grid` 样式外，**额外往 `tblPr` 注入显式 `w:tblBorders`**（top/left/bottom/right/insideH/insideV 全 single sz=4 color=999999），双保险确保 Word 一定显示边框。
- **图片内嵌**：见上方根因 ①。
- **SVG 光栅化**：见上方根因 ②。渲染前先去掉 svg 的 `style` 并把 `viewBox` 尺寸写成 `width/height` 属性，窗口大小设为 viewBox 尺寸，`--force-device-scale-factor=2` 提清晰度。
- **健壮性坑（已修）**：若 `<img>`/`<svg>` 恰好嵌在 `<h4>` 等标题标签内部（HTML 解析后 parent 是 heading 段落），`add_inline` 要能识别并把图片加到段落的**块容器**（`paragraph._parent`）而非段落本身（段落无 `add_paragraph` 方法，否则会 `AttributeError`）。

## 转换后必做「排版排查」自检

转完跑一段校验（参考下方），确认无误再交付：

```python
from docx import Document
from docx.oxml.ns import qn
d = Document("out.docx")
assert len(d.inline_shapes) >= 期望图片数   # 截图+流程图全部在内
assert all(t._tbl.tblPr.find(qn('w:tblBorders')) is not None for t in d.tables)  # 表有边框
# 抽查中文未乱码、标题层级(Title/Heading1/2)齐全

# ⚠️ 标题吞正文/重复检查（必须 suspect=0）
for p in d.paragraphs:
    if p.style.name.startswith('Heading') or p.style.name == 'Title':
        assert '\n' not in p.text and len(p.text) <= 60, f"标题异常: {p.text[:50]}"
```

## ⚠️ 标题重复 / 标题吞正文排查（强约束，必须做）

转换后若出现「某个标题文本极长、包含后续章节标题名、或大小标题内容错乱重复」，根因是**源 HTML 的 h1-h6 标题标签开闭名不匹配**：

- 反例：`<h4>4.2.2 详细逻辑规则</h5>`（开 h4 闭 h5）、`<h3>4.4 ...</h4>`（开 h3 闭 h4）
- 后果：`html.parser` 遇到不匹配的闭合标签会失效，该标题**实际未闭合**，后续整段内容（含其它标题文本）被解析为它的子节点，转换器再把子节点全文塞进标题段落 → 表现为「标题巨大 / 内容重复错乱」。
- 浏览器里显示正常（浏览器会隐式闭合标题），所以肉眼看 HTML 不易发现，必须靠转换后自检。

**两层防御：**
1. **源文件优先修正**：转换前 grep 检查 `<h[1-6]>` 开标签与 `</h[1-6]>` 闭合是否同名成对；不匹配则直接改源 HTML（只改闭合标签名，保持层级不变）。
2. **转换器内置兜底**：`unwrap_heading_blocks()` 预处理会把标题内错误嵌套的【直接块级子节点】（h4/table/div/...）提升到与标题同级；`add_heading()` 只取标题的**直接文本 + 直接行内子节点**，不再递归吞块级。

**转换后必查（脚本已自动打印 `HEADING HEALTH: suspect=N`）**：
- 遍历所有 Heading/Title 段落，若某标题文本含 `\n` 或长度 > 60 字符 → 判为「标题吞正文」异常，必须回头修源 HTML 标签配对，不能交付。
- 正常：suspect=0。

## ⚠️ HTML 注释泄漏导致「标题重复」（强约束，v2.2 已修）

**现象**：Word 中每个章节标题出现两次——一次是 `═══ 章节名 ═══` 样式的分隔线文本，一次是正式的 hN 标题。

**根因**：源 HTML 中有章节分隔注释如 `<!-- ═══════════ 一、文档基本信息 ═══════════ -->`。bs4 的 `Comment` 类是 `NavigableString` 的子类，转换器 `add_block()` 中 `isinstance(child, NavigableString)` 会匹配到 Comment 对象，`str(comment)` 返回去掉 `<!-- -->` 后的纯文本 → 被当作普通正文段落输出 → 和正式 hN 标题形成「重复」。

**修复（已固化进 v2.2 脚本）**：
- 导入 `from bs4 import Comment`
- 所有遍历 `el.children` 的函数（`add_block` / `add_heading` / `unwrap_heading_blocks`）统一在开头 `if isinstance(child, Comment): continue`
- **以后任何 HTML 源文件中的注释都不会泄漏到 Word 输出中**

**自检**：若发现 Word 中出现 `═══` 或 `----` 包裹的章节名文本 + 同名正式标题并存，即为注释泄漏，确认脚本版本 ≥ v2.2 即可。

## 已知限制

- 复杂 CSS 布局（flex/grid/绝对定位）不会还原为 Word 版式，转为线性流式文档。
- Word 不支持 `<canvas>`、`<video>`、交互脚本。
- SVG 光栅化依赖本机 msedge；若环境无 Edge，会降级为「[流程图渲染失败]」文本提示，需手动补图。
