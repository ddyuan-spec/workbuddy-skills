#!/usr/bin/env python3
"""
Convert a local HTML PRD into a DingTalk-friendly Markdown file.

- Removes <style>, <script>, <svg>, <noscript> tags.
- Converts remaining HTML to Markdown via markdownify.
- Strips redundant clipboard screenshot placeholders like
  @image#1:Clipboard_Screenshot.png or local clipboard-*.png paths.
- Keeps online image URLs (e.g. GitHub Pages / CDN) intact.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print("Install with: pip install beautifulsoup4 markdownify lxml")
    sys.exit(1)


CLIPBOARD_PATTERNS = [
    re.compile(r"@image#\d+:[^\s)]+?Clipboard[^\s)]*?\.(png|jpg|jpeg|gif)", re.I),
    re.compile(r"clipboard-[^\s)]+?\.(png|jpg|jpeg|gif)", re.I),
    re.compile(r"file:///?[^\s)]+?\.(png|jpg|jpeg|gif)", re.I),
]

LOCAL_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s)]+?\.(png|jpg|jpeg|gif)", re.I)

# 绿韵家项目 GitHub Pages 根地址；PRD HTML 中图片使用相对路径 prd-assets/xxx，
# 钉钉文档无法解析相对路径，必须补成线上绝对 URL。
LVYUNJI_BASE_URL = "https://ddyuan-spec.github.io/lvyunji/"


def clean_clipboard_references(text: str) -> str:
    """Remove or neutralize redundant clipboard/local image references."""
    for pat in CLIPBOARD_PATTERNS:
        text = pat.sub("", text)
    text = LOCAL_WINDOWS_PATH_RE.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def absolutify_image_urls(text: str, base_url: str) -> str:
    """
    把 Markdown 中的相对图片 URL 补成绝对 URL。
    仅处理未以 http/https/ftp/file/ 开头的路径；
    已绝对 / 本地绝对路径 / file:// 等保持不变。
    """

    def _replace(match: re.Match) -> str:
        alt = match.group(1)
        raw = match.group(2).strip()
        # group(2) 可能包含 title，如 url "title"；先拆出 URL 部分
        url = raw.split()[0].strip('"')
        if re.match(r"^(https?|ftp|file):", url, re.I):
            return match.group(0)
        absolute = (base_url.rstrip("/") + "/" + url.lstrip("/")).strip()
        # 保留 title 的话需要重建
        if len(raw.split()) > 1:
            title = raw[len(url):].strip()
            return f"![{alt}]({absolute} {title})"
        return f"![{alt}]({absolute})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace, text)


def extract_table_imgs(soup) -> None:
    """
    把表格单元格内嵌的 <img> 提取为表格后的独立段落。

    markdownify 会丢弃 <td> 内嵌 <img>，导致 PRD 表格里的"定义小图"
    （inactive-def / high-value-def / consume-def / contact-list / add-record 等）
    在钉钉文档中缺失。钉钉文档模型里图片是独立图块，不是表格单元格内嵌，
    因此把图片移到表格之后、作为独立段落最稳妥。
    """
    for table in soup.find_all("table"):
        imgs = table.find_all("img")
        if not imgs:
            continue
        # 先读取属性，再移除节点
        captured = [(img.get("alt", "") or "", img.get("src", "") or "") for img in imgs]
        for img in imgs:
            img.decompose()
        anchor = table
        for alt, src in captured:
            p = soup.new_tag("p")
            p.string = f"![{alt}]({src})"
            anchor.insert_after(p)
            anchor = p


def html_to_dingtalk_md(html_path: str, output_path: str | None = None) -> str:
    html_file = Path(html_path)
    if not html_file.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    html = html_file.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    # Drop tags that pollute Markdown projection
    for tag_name in ("style", "script", "svg", "noscript"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 表格内嵌图片提升为表格后独立段落（否则 markdownify 会丢弃）
    extract_table_imgs(soup)

    markdown = md(str(soup), heading_style="ATX", strip=["a"] )
    markdown = clean_clipboard_references(markdown)
    markdown = absolutify_image_urls(markdown, LVYUNJI_BASE_URL)

    if output_path:
        out = Path(output_path)
        out.write_text(markdown, encoding="utf-8")
        print(f"Wrote {len(markdown)} chars to {out}")

    return markdown


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert HTML PRD to DingTalk-friendly Markdown"
    )
    parser.add_argument("input", help="Input HTML PRD file")
    parser.add_argument("output", nargs="?", help="Output Markdown file (optional)")
    args = parser.parse_args()

    try:
        html_to_dingtalk_md(args.input, args.output)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
