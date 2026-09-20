#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""钉钉发布前置门禁：检查 HTML 里的图表形态，拦截「客户端渲染图 → 钉钉裸文本」类事故。

背景（2026-09-14 事故）：swimlane 文档用 mermaid.js 客户端渲染流程图。
prd_html_to_dingtalk_md.py 会剥离 <script>（渲染器没了），但保留 .mermaid 里的**文本**，
于是钉钉文档里出现整段 `flowchart LR / subgraph / -->` 裸文本，图完全丢失。
当时 skill 只覆盖了「内联 <svg>」一种形态，mermaid 是漏网的第二形态。

本脚本在转换/推送**之前**跑，扫出所有非 <img> 的图表形态并直接判失败。

用法：
    python check_diagram_forms.py <file.html> [--json]
退出码：0 = 通过（只有 <img> 图，可安全发布）；1 = 有风险形态，必须先处理。
"""
import argparse
import json
import os
import re
import sys

# 客户端渲染 / 运行时渲染的图表库：源码里只有文本或 canvas，转换后必然丢失或变裸文本
CLIENT_SIDE = {
    "mermaid":      r'class\s*=\s*["\'][^"\']*\bmermaid\b|mermaid(?:\.min)?\.js|mermaid\.initialize',
    "echarts":      r'echarts(?:\.min)?\.js|echarts\.init',
    "chart.js":     r'chart(?:\.min)?\.js|new\s+Chart\s*\(',
    "d3":           r'd3(?:\.min)?\.js',
    "vis-network":  r'vis-network(?:\.min)?\.js',
    "cytoscape":    r'cytoscape(?:\.min)?\.js',
    "plantuml":     r'plantuml\.js|@startuml',
    "katex/mathjax": r'katex(?:\.min)?\.(?:js|css)|mathjax',
}

HINT = {
    "mermaid":       "把 <div class=\"mermaid\">…</div> 用 scripts/render_mermaid.py 渲染成 PNG，再改成 <figure class=\"flowfig\"><img src=\"…\"><figcaption>…</figcaption></figure>（与原 <img> 图同构），mermaid 源码可留 HTML 注释备查。",
    "echarts":       "图表须先截图/导出 PNG，再以 <img> 形式进文档。",
    "chart.js":      "图表须先截图/导出 PNG，再以 <img> 形式进文档。",
    "d3":            "D3 渲染结果须先导出 PNG/SVG→PNG，再以 <img> 形式进文档。",
    "vis-network":   "网络图须先导出 PNG，再以 <img> 形式进文档。",
    "cytoscape":     "关系图须先导出 PNG，再以 <img> 形式进文档。",
    "plantuml":      "PlantUML 先渲染成 PNG，再以 <img> 形式进文档。",
    "katex/mathjax": "数学公式钉钉不渲染，须转成图片或纯文本/Unicode。",
}


def strip_comments(html: str) -> str:
    """删掉 HTML 注释：作者常把渲染源留在 <!-- ... --> 里备查，不能误判为风险。"""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def strip_pre_code(html: str) -> str:
    """删掉 <pre>/<code> 区块：提示词里出现 'flowchart' 字样的教学示例不算图。"""
    html = re.sub(r"<pre\b.*?</pre>", "", html, flags=re.S | re.I)
    html = re.sub(r"<code\b.*?</code>", "", html, flags=re.S | re.I)
    return html


def scan(path: str) -> dict:
    raw = open(path, encoding="utf-8").read()
    body = strip_pre_code(strip_comments(raw))

    imgs = re.findall(r'<img\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', body, flags=re.I)
    svgs = len(re.findall(r"<svg\b", body, flags=re.I))

    hits = {}
    for name, pat in CLIENT_SIDE.items():
        n = len(re.findall(pat, body, flags=re.I))
        if n:
            hits[name] = n

    # 只有 <img> 才算「可投影到钉钉」的图；svg 与客户端渲染一律拦
    blockers = dict(hits)
    if svgs:
        blockers["inline-svg"] = svgs

    return {
        "file": os.path.basename(path),
        "img": len(imgs),
        "img_list": imgs,
        "inline_svg": svgs,
        "client_side": hits,
        "blockers": blockers,
        "pass": not blockers,
    }


def report(r: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["pass"] else 1

    print(f"=== 图表形态门禁：{r['file']} ===")
    print(f"  <img> 图（可投影，OK）: {r['img']}")
    for s in r["img_list"]:
        print(f"      - {s}")
    if r["inline_svg"]:
        print(f"  ⚠️  内联 <svg>: {r['inline_svg']}（转换时被剥离 → 图丢失）")
    if r["client_side"]:
        print(f"  ⚠️  客户端渲染图: {r['client_side']}（渲染器被剥离 → 源码裸文本进钉钉）")

    if r["pass"]:
        print("  ✅ PASS：仅 <img> 形态，可安全转换/推送。")
        return 0

    print("  ❌ FAIL：存在非 <img> 图表形态，推钉钉前必须先转成 PNG。")
    print("  处理建议：")
    for k in r["blockers"]:
        print(f"      [{k}] {HINT.get(k, '先渲染成 PNG，再以 <img> 形式进文档。')}")
    return 1


def main():
    ap = argparse.ArgumentParser(description="钉钉发布前置：图表形态门禁")
    ap.add_argument("html", help="待检查的 HTML")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()
    if not os.path.exists(a.html):
        print(f"文件不存在: {a.html}", file=sys.stderr)
        return 2
    return report(scan(a.html), a.json)


if __name__ == "__main__":
    sys.exit(main())
