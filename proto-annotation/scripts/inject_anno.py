#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给原型 HTML 注入 Annotation Overlay 引擎（幂等）。

用法:
  python inject_anno.py --html a.html
  python inject_anno.py --dir ./protos
  python inject_anno.py --html a.html --force      # 已注入时强制替换为最新引擎（用于收口/升级）

行为:
  - 读取本 skill 的 assets/engine.js + assets/engine.css，内联注入到目标 HTML 的 </body> 前。
  - 幂等：文件已含 <script id="__anno_engine"> 时直接跳过（除非 --force）。
  - --force：先剥离旧的 __anno_css/__anno_seed/__anno_engine 块，再注入最新引擎（用于把两个生产文件的旧引擎收口到 assets 单一源）。

引擎（v4 本地优先）：无域名门禁 —— 本地 file:// 直接可批注/同步（见 engine.js 头部 canAnnotate=true），
无需先推 GitHub。注入即自包含单文件原型，浏览器无法回写源文件，故「保存原型」用下载+覆盖+AI 推送完成落盘。
"""
import argparse, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(os.path.dirname(HERE), 'assets')
ENGINE_JS = open(os.path.join(ASSET_DIR, 'engine.js'), encoding='utf-8').read()
ENGINE_CSS = open(os.path.join(ASSET_DIR, 'engine.css'), encoding='utf-8').read()

RE_CSS = re.compile(r'<style id="__anno_css">.*?</style>', re.S)
RE_SEED = re.compile(r'<script id="__anno_seed" type="application/json">(.*?)</script>', re.S)
RE_ENGINE = re.compile(r'<script id="__anno_engine">.*?</script>', re.S)
RE_COMMENT = re.compile(r'<!--[^\n]*原型批注层 Annotation Overlay[^\n]*-->\n?', re.S)
HAS_ENGINE = re.compile(r'<script id="__anno_engine">')


def build_block(seed_text='[]'):
    return (
        '<style id="__anno_css">' + ENGINE_CSS + '</style>\n'
        '<script id="__anno_seed" type="application/json">' + seed_text + '</script>\n'
        '<script id="__anno_engine">' + ENGINE_JS + '</script>\n'
    )


def inject_file(path, force):
    html = open(path, encoding='utf-8').read()
    if HAS_ENGINE.search(html):
        if not force:
            print('  跳过(已含引擎):', os.path.basename(path))
            return 'skip'
        # 保留已有种子（线上批注数据），避免 --force 误清空
        m = RE_SEED.search(html)
        seed_text = m.group(1) if m else '[]'
        try:
            json.loads(seed_text)
        except Exception:
            seed_text = '[]'
        html = RE_COMMENT.sub('', html)
        html = RE_CSS.sub('', html)
        html = RE_SEED.sub('', html)
        html = RE_ENGINE.sub('', html)
        print('  已剥离旧引擎，准备重注入:', os.path.basename(path))
    else:
        seed_text = '[]'
    block = build_block(seed_text)
    # 注入到「真实文档末尾」的 </body> 前：取文件中【最后一个】</body>，
    # 避免命中 JS 字符串里的 '... </body> ...'（如 C 端原型 __protoBuildStandalone 的返回值）。
    # 若取第一个会误插进 JS 字符串，导致批注层不进真实 DOM、且「复制源码」功能被截断。
    last = None
    for mm in re.finditer(r'</body>', html, re.I):
        last = mm
    if last is not None:
        html = html[:last.start()] + block + html[last.start():]
    else:
        html = html + '\n' + block
    open(path, 'w', encoding='utf-8').write(html)
    print('  已注入引擎:', os.path.basename(path))
    return 'injected'


def main():
    ap = argparse.ArgumentParser(description='注入原型批注引擎（幂等）')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--html', help='单个 HTML 文件')
    g.add_argument('--dir', help='目录，批量注入目录下所有 *.html')
    ap.add_argument('--force', action='store_true', help='已注入时强制替换为最新引擎')
    args = ap.parse_args()

    if args.html:
        paths = [args.html]
    else:
        paths = sorted(glob.glob(os.path.join(args.dir, '*.html')))
        if not paths:
            sys.exit('目录下没有 .html 文件: ' + args.dir)

    print('注入目标数:', len(paths))
    inj = skip = 0
    for p in paths:
        r = inject_file(p, args.force)
        if r == 'injected':
            inj += 1
        elif r == 'skip':
            skip += 1
    print('完成: 注入 %d, 跳过 %d' % (inj, skip))


if __name__ == '__main__':
    main()
