#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
html_to_docx.py  ——  高保真 HTML -> Word(.docx) 转换器
解决两类「Word 图片缺失」根因：
  1) 相对路径 <img src="xxx.png">  —— 改为读取本地字节并 add_picture 内嵌（不再依赖外部文件）
  2) 内联 <svg> 矢量图  ——  Word 不支持 SVG，先用 msedge headless 光栅化为 PNG 再内嵌
同时保留：标题层级 / 表格边框(Table Grid + 显式边框) / 列表 / 加粗 / 链接 / 颜色 / 中文(eastAsia 字体)。
用法：python html_to_docx.py <input.html> <output.docx> [--edge <msedge.exe>]
"""
import sys, os, re, io, subprocess, argparse
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BLOCK_TAGS = {"p","ul","ol","table","div","section","h1","h2","h3","h4","h5","img","svg"}

def find_edge():
    for p in [r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
              r"C:/Program Files/Microsoft/Edge/Application/msedge.exe"]:
        if os.path.exists(p): return p
    return "msedge"

def set_cjk(style, font="Microsoft YaHei"):
    style.font.name = font
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:eastAsia"), font)

def shade(paragraph, fill="F8FAFC"):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'),'clear'); shd.set(qn('w:color'),'auto'); shd.set(qn('w:fill'), fill)
    pPr.append(shd)

def add_hyperlink(paragraph, url, text):
    if not text: return
    part = paragraph.part
    rId = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement('w:hyperlink'); hyperlink.set(qn('r:id'), rId)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr'); rStyle = OxmlElement('w:rStyle'); rStyle.set(qn('w:val'),'Hyperlink')
    rPr.append(rStyle); new_run.append(rPr)
    t = OxmlElement('w:t'); t.text = text; new_run.append(t)
    hyperlink.append(new_run); paragraph._p.append(hyperlink)

def add_inline(paragraph, node, bold=False):
    if isinstance(node, NavigableString):
        t = str(node)
        if t == "": return
        run = paragraph.add_run(t); run.bold = bold
        return
    tag = node.name
    if tag in ("b","strong"):
        for ch in node.children: add_inline(paragraph, ch, bold=True)
    elif tag == "code":
        for ch in node.children:
            run = paragraph.add_run(str(ch) if isinstance(ch,NavigableString) else ch.get_text())
            run.font.name = "Consolas"; run.font.color.rgb = RGBColor(0xbe,0x12,0x3c)
    elif tag == "a":
        add_hyperlink(paragraph, node.get("href",""), node.get_text())
    elif tag in ("span","em","i","font"):
        for ch in node.children: add_inline(paragraph, ch, bold=bold)
    elif tag == "br":
        paragraph.add_run().add_break()
    elif tag == "img":
        add_img(paragraph._parent, node)
    elif tag == "svg":
        add_svg(paragraph._parent, node)
    else:
        for ch in node.children: add_inline(paragraph, ch, bold=bold)

def add_list(parent, el, ordered):
    for li in el.find_all("li", recursive=False):
        p = parent.add_paragraph(style="List Number" if ordered else "List Bullet")
        for ch in li.children:
            if isinstance(ch, NavigableString): add_inline(p, ch)
            elif ch.name in ("ul","ol"): add_list(parent, ch, ch.name=="ol")
            else: add_inline(p, ch)

def add_img(parent, el, width=6.0):
    src = el.get("src","")
    alt = el.get("alt","")
    if not src or src.startswith("http"):
        if alt:
            p = parent.add_paragraph(); add_inline(p, NavigableString(alt))
        return
    path = os.path.join(BASE, src)
    if not os.path.exists(path):
        if alt:
            p = parent.add_paragraph(); r = p.add_run("[缺失图片] "+alt); r.font.color.rgb=RGBColor(0xdc,0x26,0x26)
        return
    p = parent.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    with open(path,"rb") as f: data = f.read()
    p.add_run().add_picture(io.BytesIO(data), width=Inches(width))
    if alt:
        cap = parent.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(alt); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x6b,0x72,0x80)

def add_svg(parent, el, width=6.2):
    global SVG_COUNTER
    idx = SVG_COUNTER; SVG_COUNTER += 1
    png = SVG_PNGS[idx] if idx < len(SVG_PNGS) else None
    if png and os.path.exists(png):
        p = parent.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        with open(png,"rb") as f: data = f.read()
        p.add_run().add_picture(io.BytesIO(data), width=Inches(width))
    else:
        parent.add_paragraph().add_run("[流程图渲染失败]").font.color.rgb = RGBColor(0xdc,0x26,0x26)

def set_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    existing = tblPr.find(qn('w:tblBorders'))
    if existing is not None: tblPr.remove(existing)
    borders = OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4')
        e.set(qn('w:space'),'0'); e.set(qn('w:color'),'999999')
        borders.append(e)
    tblPr.append(borders)

def add_table(parent, el):
    rows = el.find_all("tr")
    if not rows: return
    n_cols = max(len(r.find_all(["td","th"])) for r in rows)
    t = parent.add_table(rows=len(rows), cols=n_cols)
    try: t.style = "Table Grid"
    except Exception: pass
    set_table_borders(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, r in enumerate(rows):
        cells = r.find_all(["td","th"])
        is_header = (r.find_parent("thead") is not None) or (cells and cells[0].name == "th")
        for ci in range(n_cols):
            cell = t.cell(ri, ci); cell.text = ""
            if ci >= len(cells): continue
            c = cells[ci]
            block_ch = [ch for ch in c.children if not isinstance(ch, NavigableString)]
            has_block = any(bc.name in ("p","ul","ol","div","table") for bc in block_ch)
            first = True
            if has_block:
                for ch in c.children:
                    if isinstance(ch, NavigableString):
                        if str(ch).strip():
                            para = cell.paragraphs[0] if first else cell.add_paragraph()
                            add_inline(para, ch); first = False
                    elif ch.name in ("p","div"):
                        para = cell.paragraphs[0] if first else cell.add_paragraph()
                        add_inline(para, ch); first = False
                    elif ch.name in ("ul","ol"):
                        add_list(cell, ch, ch.name=="ol"); first = False
                    else:
                        para = cell.paragraphs[0] if first else cell.add_paragraph()
                        add_inline(para, ch); first = False
            else:
                add_inline(cell.paragraphs[0], c)
            if is_header:
                for para in cell.paragraphs:
                    for run in para.runs: run.bold = True

def add_heading(parent, el, level):
    p = parent.add_paragraph()
    try:
        p.style = doc.styles["Title"] if level == 0 else doc.styles[f"Heading {level}"]
    except Exception:
        pass
    add_inline(p, el)

def div_has_block(el):
    for ch in el.children:
        if not isinstance(ch, NavigableString) and ch.name in BLOCK_TAGS:
            return True
    return False

def add_block(parent, el):
    for child in el.children:
        if isinstance(child, NavigableString):
            if str(child).strip():
                p = parent.add_paragraph(); add_inline(p, child)
            continue
        name = child.name
        if name == "h1": add_heading(parent, child, 0)
        elif name == "h2": add_heading(parent, child, 1)
        elif name == "h3": add_heading(parent, child, 2)
        elif name == "h4": add_heading(parent, child, 3)
        elif name == "h5": add_heading(parent, child, 4)
        elif name == "p":
            p = parent.add_paragraph(); add_inline(p, child)
        elif name in ("ul","ol"): add_list(parent, child, name=="ol")
        elif name == "table": add_table(parent, child)
        elif name == "img": add_img(parent, child)
        elif name == "svg": add_svg(parent, child)
        elif name in ("div","section"):
            cls = child.get("class", []) or []
            if div_has_block(child):
                add_block(parent, child)
            else:
                p = parent.add_paragraph()
                if "note" in cls: shade(p)
                if "pending" in cls: shade(p, "FFF7ED")
                add_inline(p, child)
        else:
            add_block(parent, child)

def render_svgs(soup, edge, tmp):
    nodes = soup.find_all("svg")
    out = []
    for i, svg in enumerate(nodes):
        vb = svg.get("viewBox", "0 0 1000 500").split()
        w, h = int(vb[2]), int(vb[3])
        s = str(svg)
        s = re.sub(r'style="[^"]*"', '', s)
        s = re.sub(r'<svg\b', f'<svg width="{w}" height="{h}"', s, count=1)
        wrap = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#fff;">{s}</body></html>'
        html_path = f"{tmp}/svg_{i}.html"
        png_path = f"{tmp}/svg_{i}.png"
        open(html_path,"w",encoding="utf-8").write(wrap)
        url = "file:///" + html_path.replace("\\","/")
        subprocess.run([edge,"--headless=new","--disable-gpu","--no-sandbox","--hide-scrollbars",
                        "--force-device-scale-factor=2","--window-size=%d,%d"%(w,h),
                        "--screenshot="+png_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out.append(png_path)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--edge", default=None)
    args = ap.parse_args()
    SRC = os.path.abspath(args.input); BASE = os.path.dirname(SRC)
    OUT = os.path.abspath(args.output)
    EDGE = args.edge or find_edge()
    TMP = os.path.join(os.path.dirname(OUT), "_docx_tmp")
    os.makedirs(TMP, exist_ok=True)

    raw = open(SRC, encoding="utf-8").read()
    soup = BeautifulSoup(raw, "html.parser")

    SVG_PNGS = render_svgs(soup, EDGE, TMP)
    SVG_COUNTER = 0

    doc = Document()
    set_cjk(doc.styles["Normal"]); doc.styles["Normal"].font.size = Pt(10.5)
    for lvl in (0,1,2,3,4):
        try:
            set_cjk(doc.styles["Title"] if lvl==0 else doc.styles[f"Heading {lvl}"])
        except Exception: pass

    body = soup.body or soup
    add_block(doc, body)
    doc.save(OUT)
    print(f"OK saved {OUT} | svgs rendered={len(SVG_PNGS)} inline_images={len(doc.inline_shapes)} paragraphs={len(doc.paragraphs)} tables={len(doc.tables)}")
