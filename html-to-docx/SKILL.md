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
```

## 已知限制

- 复杂 CSS 布局（flex/grid/绝对定位）不会还原为 Word 版式，转为线性流式文档。
- Word 不支持 `<canvas>`、`<video>`、交互脚本。
- SVG 光栅化依赖本机 msedge；若环境无 Edge，会降级为「[流程图渲染失败]」文本提示，需手动补图。
