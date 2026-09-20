#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内联 <svg> → 白底紧裁 PNG（Edge/Chromium headless，viewBox 定尺寸，无需 mermaid.js）。

为什么存在：钉钉 Markdown 不渲染内联 <svg>，转换时被剥离 → 图直接丢失
（check_diagram_forms.py 检出 inline-svg 后必须先走本脚本）。mermaid 用
render_mermaid.py；本脚本只管 HTML 里现成的内联 <svg>（流程图/状态机等手绘图）。

用法：
    # 渲染所有内联 svg 到 out-dir（默认不改动 HTML）
    python render_inline_svg.py --html doc.html --out-dir ./out --prefix doc
    # 渲染 + 直接把 <div class="fig"><svg>…</svg></div> 替换为 <div class="fig"><img …></div>
    python render_inline_svg.py --html doc.html --out-dir ./out --prefix doc --replace
    # 常用参数：--scale 2（2x 密度，默认）、--chrome 指定浏览器路径
退出码：0 全部成功；1 有失败。
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import pathname2url


def find_chrome(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    for env in ("MERMAID_CHROME", "CHROME_PATH"):
        if os.environ.get(env):
            cands.append(os.environ[env])
    here = os.path.expanduser("~")
    cands += [
        os.path.join(here, "AppData/Local/ms-playwright/*/chrome-win64/chrome.exe"),
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    ]
    for c in cands:
        if not c:
            continue
        if os.path.isfile(c):
            return c
        for g in sorted(glob.glob(c), reverse=True):
            if os.path.isfile(g):
                return g
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def extract_blocks(html):
    """按出现顺序取内联 <svg> 块；优先带 <div class="fig"> 包装的（可替换），否则裸 svg。"""
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)  # 先删注释，避免把备查源码当图
    wrapped = re.findall(r'<div class="fig">\s*(<svg[\s\S]*?</svg>)\s*</div>', html)
    if wrapped:
        return wrapped, True
    return re.findall(r"<svg[\s\S]*?</svg>", html), False


def svg_size(svg):
    m = re.search(r'viewBox=["\']0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)["\']', svg)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'<svg[^>]*width=["\'](\d+)[^>]*height=["\'](\d+)', svg)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 900.0, 600.0


def svg_caption(svg, idx):
    m = re.search(r"图\s*\d+(?:-\d+)?[^<>{]{0,40}", re.sub(r"<[^>]+>", "", svg))
    return m.group(0).strip() if m else f"图 {idx}"


def render_one(svg, out_png, chrome, scale=2):
    from PIL import Image, ImageChops
    w, h = svg_size(svg)
    pad = 20
    wrap = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;padding:0;background:#fff}"
            "svg{width:%dpx!important;height:%dpx!important;display:block}"
            "</style></head><body>%s</body></html>" % (int(w), int(h), svg))
    tmpdir = tempfile.mkdtemp(prefix="svg_")
    try:
        tmp_html = os.path.join(tmpdir, "d.html")
        open(tmp_html, "w", encoding="utf-8").write(wrap)
        tmp_png = os.path.join(tmpdir, "shot.png")
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--no-sandbox", "--force-color-profile=srgb",
               "--force-device-scale-factor=%s" % scale,
               "--window-size=%d,%d" % (int(w) + pad, int(h) + pad),
               "--virtual-time-budget=8000", "--screenshot=" + tmp_png,
               "file:///" + pathname2url(tmp_html).lstrip("/")]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not os.path.exists(tmp_png):
            return False, None
        im = Image.open(tmp_png).convert("RGB")
        bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
        if bbox:
            p = 16
            im = im.crop((max(0, bbox[0] - p), max(0, bbox[1] - p),
                          min(im.width, bbox[2] + p), min(im.height, bbox[3] + p)))
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        im.save(out_png, "PNG")
        return True, (im.width, im.height)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="内联 <svg> → PNG（钉钉发布前置渲染）")
    ap.add_argument("--html", required=True, help="含内联 <svg> 的 HTML")
    ap.add_argument("--out-dir", help="输出目录（默认 HTML 同目录）")
    ap.add_argument("--prefix", default="diagram", help="输出文件名前缀")
    ap.add_argument("--scale", type=int, default=2, help="像素密度倍数（默认 2）")
    ap.add_argument("--chrome", help="chromium/chrome/Edge 可执行文件")
    ap.add_argument("--replace", action="store_true",
                    help="渲染后把 <div class=\"fig\"><svg>…</svg></div> 原地替换为 <img> 图式")
    a = ap.parse_args()

    chrome = find_chrome(a.chrome)
    if not chrome:
        print("找不到 chromium/chrome/Edge，请用 --chrome 指定", file=sys.stderr)
        return 2
    html = open(a.html, encoding="utf-8").read()
    blocks, wrappable = extract_blocks(html)
    if not blocks:
        print("HTML 里没有内联 <svg> 块（可能已转换过）")
        return 0
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.html))
    print(f"[render_inline_svg] chrome={chrome}  svg块={len(blocks)}")

    ok_all, png_names, results = True, [], []
    for i, svg in enumerate(blocks, 1):
        out_png = os.path.join(out_dir, f"{a.prefix}-{i}.png")
        ok, size = render_one(svg, out_png, chrome, a.scale)
        ok_all = ok_all and ok
        png_names.append(f"{a.prefix}-{i}.png")
        results.append({"index": i, "out": out_png, "ok": ok, "size": size})
        print(f"  [{'OK' if ok else 'FAIL'}] {os.path.basename(out_png)}"
              + (f"  {size[0]}x{size[1]}" if ok and size else ""))

    if a.replace:
        if not wrappable:
            print("  [SKIP] --replace 仅支持 <div class=\"fig\"> 包装的 svg 块（当前为裸 svg，请手工替换）")
        else:
            idx = [0]

            def repl(m):
                i = idx[0]
                idx[0] += 1
                cap = svg_caption(blocks[i], i + 1)
                src = f"{a.prefix}-{i + 1}.png"
                return (f'<div class="fig"><img class="shot-admin" src="{src}" alt="{cap}">'
                        f'<div class="fig-cap">{cap}</div></div>')

            html2 = re.sub(r'<div class="fig">\s*<svg[\s\S]*?</svg>\s*</div>', repl, html)
            open(a.html, "w", encoding="utf-8").write(html2)
            print(f"  [REPLACE] 已替换 {idx[0]} 块为 <img>（src 相对路径，推送前确认 PNG 随 HTML 一起发布）")

    print(f"[render_inline_svg] 完成 {sum(1 for r in results if r['ok'])}/{len(results)}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
