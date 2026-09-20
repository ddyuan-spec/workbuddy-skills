#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mermaid 文本 → 白底紧裁 PNG（chromium headless，两趟：先量后截）。

为什么存在：钉钉 Markdown 不渲染 mermaid / 内联 <svg>，客户端渲染图进钉钉只会变成
裸文本（2026-09-14 swimlane 事故）。所有流程图/泳道图/时序图必须先渲染成 PNG，
再以 <img> 形式进文档。本脚本是这一步的固化实现，别再现场手写截图脚本。

用法：
    # 单个 .mmd 文件
    python render_mermaid.py --mmd flow.mmd --out flow.png
    # 从 HTML 里批量渲染所有 <div class="mermaid"> 块
    python render_mermaid.py --html doc.html --out-dir ./out --prefix doc
    # 常用参数
    --scale 2            2 倍像素密度（默认 2，够钉钉缩放看）
    --mermaid-js PATH    指定本地 mermaid.min.js（默认自动缓存/下载 CDN）
    --chrome PATH        指定 chromium/chrome 可执行文件（默认自动探测）
    --json               机器可读输出
退出码：0 全部成功；1 有失败。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import pathname2url

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_DIR, "_cache")
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

HTML_TPL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>PENDING</title>
<style>
  html,body {{ margin:0; padding:0; background:#ffffff; }}
  #wrap {{ display:inline-block; padding:24px; background:#ffffff; }}
  .mermaid {{ background:transparent; border:none; padding:0; margin:0; }}
  .mermaid svg {{ max-width:none !important; height:auto !important; }}
</style>
<script src="file:///{js}"></script>
</head><body>
<div id="wrap"><div class="mermaid">
{code}
</div></div>
<script>
  mermaid.initialize({{ startOnLoad:true, theme:'default',
    flowchart:{{ useMaxWidth:false, htmlLabels:true, curve:'basis' }},
    sequence:{{ useMaxWidth:false, wrap:false }} }});
  (function poll(n){{
    var svg = document.querySelector('.mermaid svg');
    if (svg) {{ var b = svg.getBoundingClientRect();
      document.title = Math.ceil(b.width)+'x'+Math.ceil(b.height); }}
    else if (n < 150) {{ setTimeout(function(){{ poll(n+1); }}, 100); }}
    else {{ document.title = '0x0'; }}
  }})(0);
</script>
</body></html>
"""


# ---------- 依赖探测 ----------

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
        os.path.join(here, ".cache/ms-playwright/*/chrome-linux/chrome"),
        os.path.join(here, "Library/Caches/ms-playwright/*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
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


def find_mermaid_js(explicit=None):
    if explicit:
        if not os.path.isfile(explicit):
            raise FileNotFoundError(f"--mermaid-js 不存在: {explicit}")
        return explicit
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.join(CACHE_DIR, "mermaid.min.js")
    if os.path.isfile(cached) and os.path.getsize(cached) > 1000:
        return cached
    import urllib.request
    print(f"[render_mermaid] 下载 mermaid.min.js → {cached}")
    urllib.request.urlretrieve(MERMAID_CDN, cached)
    return cached


# ---------- 渲染 ----------

def _build_html(code, mermaid_js, out_html):
    open(out_html, "w", encoding="utf-8").write(
        HTML_TPL.format(js=mermaid_js.replace("\\", "/"), code=code))


def _run(cmd, timeout=240):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _measure(html_path, chrome):
    r = _run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
              "--virtual-time-budget=12000", "--dump-dom",
              "file:///" + pathname2url(html_path).lstrip("/")])
    m = re.search(r"<title>(\d+)x(\d+)</title>", r.stdout or "")
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    return (w, h) if w > 0 and h > 0 else None


def render_one(code, out_png, mermaid_js, chrome, scale=2):
    from PIL import Image, ImageChops
    tmpdir = tempfile.mkdtemp(prefix="mm_")
    try:
        tmp_html = os.path.join(tmpdir, "d.html")
        _build_html(code, mermaid_js, tmp_html)
        size = _measure(tmp_html, chrome)
        if size is None:
            print("  [FAIL] 量不到 svg，可能 mermaid 未渲染（语法错误？）")
            return False
        w, h = size[0] + 80, size[1] + 80
        tmp_png = os.path.join(tmpdir, "shot.png")
        _run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
              "--no-sandbox", "--force-color-profile=srgb",
              f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
              "--virtual-time-budget=12000", f"--screenshot={tmp_png}",
              "file:///" + pathname2url(tmp_html).lstrip("/")])
        if not os.path.exists(tmp_png):
            print("  [FAIL] 截图未产出")
            return False
        im = Image.open(tmp_png).convert("RGB")
        bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
        if bbox:
            pad = 16
            im = im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                          min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad)))
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        im.save(out_png, "PNG")
        print(f"  [OK] {os.path.basename(out_png)}  {im.width}x{im.height}  {os.path.getsize(out_png)}B")
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def extract_blocks(html_path):
    """按出现顺序取出所有 <div class="mermaid"> 块（先删注释，避免把备查源码当图）。"""
    raw = open(html_path, encoding="utf-8").read()
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    return [m.strip() for m in
            re.findall(r'<div[^>]*class\s*=\s*["\'][^"\']*\bmermaid\b[^"\']*["\'][^>]*>(.*?)</div>',
                       raw, flags=re.S | re.I)]


def kind_of(code):
    return code.splitlines()[0].strip() if code.strip() else "?"


def main():
    ap = argparse.ArgumentParser(description="mermaid → PNG（钉钉发布前置渲染）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--mmd", help="单个 .mmd 文件")
    g.add_argument("--html", help="含 <div class=\"mermaid\"> 的 HTML，批量渲染")
    ap.add_argument("--out", help="--mmd 模式的输出 PNG")
    ap.add_argument("--out-dir", help="--html 模式的输出目录")
    ap.add_argument("--prefix", default="diagram", help="--html 模式输出文件名前缀")
    ap.add_argument("--scale", type=int, default=2, help="像素密度倍数（默认 2）")
    ap.add_argument("--mermaid-js", help="本地 mermaid.min.js")
    ap.add_argument("--chrome", help="chromium/chrome 可执行文件")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    chrome = find_chrome(a.chrome)
    if not chrome:
        print("找不到 chromium/chrome，请用 --chrome 指定", file=sys.stderr)
        return 2
    try:
        mjs = find_mermaid_js(a.mermaid_js)
    except Exception as e:
        print(f"取 mermaid.min.js 失败: {e}", file=sys.stderr)
        return 2
    if not a.json:
        print(f"[render_mermaid] chrome={chrome}")
        print(f"[render_mermaid] mermaid.js={mjs}")

    results = []
    if a.mmd:
        if not a.out:
            print("--mmd 模式需要 --out", file=sys.stderr)
            return 2
        code = open(a.mmd, encoding="utf-8").read()
        ok = render_one(code, a.out, mjs, chrome, a.scale)
        results.append({"src": a.mmd, "kind": kind_of(code), "out": a.out, "ok": ok})
    else:
        blocks = extract_blocks(a.html)
        if not blocks:
            print("HTML 里没有 <div class=\"mermaid\"> 块（可能已转换过）")
            return 0
        out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.html))
        for i, code in enumerate(blocks, 1):
            out_png = os.path.join(out_dir, f"{a.prefix}-{i}.png")
            ok = render_one(code, out_png, mjs, chrome, a.scale)
            results.append({"src": a.html, "index": i, "kind": kind_of(code),
                            "out": out_png, "ok": ok})

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"[render_mermaid] 完成 {sum(1 for r in results if r['ok'])}/{len(results)}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
