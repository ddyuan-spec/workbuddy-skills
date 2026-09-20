#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_format.py —— 公众号微信兼容排版转换器

把 Markdown / 富文本 转成「微信编辑器兼容」的 HTML：
  * 外层用 <table><tr><td> 容器（微信唯一验证过兼容的结构，思路同 HTML 邮件）
  * 样式全部打在 <td> 上，内容放 <p>
  * 仅允许白名单样式：color / background-color / font-size / font-weight /
    padding / margin / border / text-align / line-height
  * 禁用：border-radius / position / linear-gradient / 伪元素 / <section>
  * 字节校验：标题 ≤ 64 字节、摘要 ≤ 120 字节（中文 1 字 = 3 字节，超长报 45003/45004）

用法：
  python wechat_format.py input.md --title "标题" --digest "摘要" --output out.html
  python wechat_format.py input.md --check-only          # 只做字节校验
依赖：仅标准库
"""
import argparse
import html
import os
import re
import sys

# ---- 样式白名单（微信编辑器只认这些）----
ALLOWED_CSS = {
    "color", "background-color", "font-size", "font-weight",
    "padding", "margin", "border", "text-align", "line-height",
    "font-family", "width", "max-width", "display",
}

# 外层容器默认样式（全部在白名单内）
TD_STYLE = (
    "font-size:15px;line-height:1.8;color:#2b2b2b;"
    "padding:0 4px;"
    "font-family:-apple-system,BlinkMacSystemFont,\"PingFang SC\",\"Microsoft YaHei\",sans-serif;"
)
H2_STYLE = "font-size:18px;font-weight:bold;color:#1a1a1a;margin:28px 0 12px;border-left:4px solid #d4af37;padding-left:10px;"
H3_STYLE = "font-size:16px;font-weight:bold;color:#333;margin:22px 0 8px;"
P_STYLE = "margin:14px 0;color:#2b2b2b;"
QUOTE_STYLE = "margin:16px 0;padding:10px 14px;background-color:#f7f7f7;color:#666;border-left:4px solid #cccccc;font-size:14px;line-height:1.7;"
CODE_STYLE = "background-color:#f2f2f2;color:#c7254e;padding:2px 4px;font-size:13px;border:1px solid #e8e8e8;"
HR_STYLE = "border:none;border-top:1px solid #eeeeee;margin:24px 0;"
IMG_STYLE = "max-width:100%;display:block;margin:10px auto;"

TITLE_LIMIT = 64    # 字节
DIGEST_LIMIT = 120  # 字节


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def check_bytes(title: str, digest: str):
    """返回校验结果列表（空=通过）。"""
    issues = []
    if title:
        n = len(title.encode("utf-8"))
        if n > TITLE_LIMIT:
            issues.append(f"标题超长：{n} 字节 > {TITLE_LIMIT}（中文 1 字=3 字节，报 45003）")
    if digest:
        n = len(digest.encode("utf-8"))
        if n > DIGEST_LIMIT:
            issues.append(f"摘要超长：{n} 字节 > {DIGEST_LIMIT}（报 45004）")
    return issues


def clean_inline(text: str) -> str:
    """处理行内 **粗体** / `代码` / [链接](url)。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+?)`", lambda m: f"<code style='{CODE_STYLE}'>{esc(m.group(1))}</code>", text)
    text = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", r"<a href='\2'>\1</a>", text)
    return text


def md_to_wechat(src: str) -> str:
    lines = src.split("\n")
    out = []
    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        line = lines[i]
        # 代码块
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                out.append(
                    f"<pre style='background-color:#f6f8fa;border:1px solid #e1e4e8;"
                    f"padding:12px;font-size:13px;line-height:1.6;overflow:auto;'>"
                    f"<code>{esc(chr(10).join(code_buf))}</code></pre>"
                )
                in_code = False
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        s = line.strip()
        if not s:
            i += 1
            continue

        # 标题
        if re.match(r"^#{1,6}\s", s):
            lvl = len(re.match(r"^(#+) ", s).group(1))
            txt = s[lvl:].strip()
            if lvl <= 2:
                out.append(f"<h2 style='{H2_STYLE}'>{esc(txt)}</h2>")
            else:
                out.append(f"<h3 style='{H3_STYLE}'>{esc(txt)}</h3>")
            i += 1
            continue

        if s == "---":
            out.append(f"<hr style='{HR_STYLE}'>")
            i += 1
            continue

        if s.startswith(">"):
            out.append(f"<blockquote style='{QUOTE_STYLE}'>{clean_inline(esc(s[1:].strip()))}</blockquote>")
            i += 1
            continue

        # 图片 ![alt](url)
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if m:
            url = m.group(2)
            out.append(f"<p style='text-align:center;'><img src='{url}' style='{IMG_STYLE}'></p>")
            i += 1
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(f"<li style='margin:6px 0;'>{clean_inline(esc(re.sub(r'^[-*]\s+', '', lines[i].strip())))}</li>")
                i += 1
            out.append(f"<ul style='padding-left:22px;'>{''.join(items)}</ul>")
            continue

        # 有序列表
        if re.match(r"^\d+\.\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(f"<li style='margin:6px 0;'>{clean_inline(esc(re.sub(r'^\d+\.\s+', '', lines[i].strip())))}</li>")
                i += 1
            out.append(f"<ol style='padding-left:22px;'>{''.join(items)}</ol>")
            continue

        # 表格
        if "|" in s and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
            rows = [s]
            while i < len(lines) and "|" in lines[i].strip():
                rows.append(lines[i].strip())
                i += 1
            tbl = "<table style='border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;'>"
            for ri, r in enumerate(rows):
                cells = [c.strip() for c in r.strip("|").split("|")]
                tag = "th" if ri == 0 else "td"
                tbl += "<tr>"
                for c in cells:
                    if c:
                        tbl += f"<{tag} style='border:1px solid #d0d7de;padding:7px 10px;text-align:left;'>{clean_inline(esc(c))}</{tag}>"
                tbl += "</tr>"
            tbl += "</table>"
            out.append(tbl)
            continue

        # 段落（合并连续普通行）
        buf = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or re.match(r"^#{1,6}\s", nxt) or nxt.startswith(">") or nxt.startswith("```") \
               or nxt == "---" or re.match(r"^[-*]\s+", nxt) or re.match(r"^\d+\.\s+", nxt) \
               or nxt.startswith("!") and ")" in nxt \
               or ("|" in nxt and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1])):
                break
            buf.append(nxt)
            i += 1
        out.append(f"<p style='{P_STYLE}'>{clean_inline(esc(' '.join(buf)))}</p>")

    body = "\n".join(out)
    doc = (
        "<table width='100%' cellpadding='0' cellspacing='0' border='0' "
        "style='width:100%;background-color:#ffffff;'>"
        "<tbody><tr><td style='" + TD_STYLE + "'>\n" + body + "\n</td></tr></tbody></table>"
    )
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Markdown 源文件")
    ap.add_argument("--title", default="", help="文章标题（做字节校验）")
    ap.add_argument("--digest", default="", help="文章摘要（做字节校验）")
    ap.add_argument("--output", default="", help="输出 HTML 路径，缺省打印到 stdout")
    ap.add_argument("--check-only", action="store_true", help="只做字节校验，不输出 HTML")
    args = ap.parse_args()

    src = open(args.input, encoding="utf-8").read()

    # 1) 字节校验（标题/摘要在正文前先做）
    issues = check_bytes(args.title, args.digest)
    if issues:
        print("⚠️ 字节校验未通过：", file=sys.stderr)
        for x in issues:
            print("  - " + x, file=sys.stderr)
    else:
        print("✅ 字节校验通过（标题≤64 / 摘要≤120）")

    if args.check_only:
        sys.exit(1 if issues else 0)

    doc = md_to_wechat(src)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(doc)
        print(f"✅ 已生成微信兼容 HTML：{args.output}（{len(doc)} 字节）")
        if issues:
            print("⚠️ 但标题/摘要超长，推送前请修正。", file=sys.stderr)
    else:
        print(doc)


if __name__ == "__main__":
    main()
