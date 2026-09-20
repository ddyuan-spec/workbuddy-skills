#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把导出的原型批注 JSON 写回源 HTML 的 __anno_seed 并推送 GitHub Pages。

这是「批注同步 GitHub」的固化推送器，复用 gh_push.py（优先本目录，回退 delivery-suite）。

用法:
  python anno_push.py --repo ddyuan-spec/lvyunji --root DIR \
      --anno lvyunji-product-admin-watercard.anno.json \
      --html lvyunji-product-admin-watercard.html \
      --message "同步批注"

流程:
  1. 读 <file>.anno.json（浏览器「同步」按钮导出的批注数组）
  2. 去掉导出时附加的 valid 等非权威字段，仅保留 id/no/view/sel/text/ts
  3. 替换源 HTML 的 <script id="__anno_seed"> 内容（一行替换，幂等）
  4. 委托 gh_push.py --put 源 HTML 到 GitHub Pages，并 --wait-pages 等构建
"""
import argparse, json, os, re, subprocess, sys

KEEP = ('id', 'no', 'view', 'sel', 'text', 'ts')


def resolve_gh_push(explicit):
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, 'gh_push.py')
    if os.path.exists(cand):
        return cand
    # 回退到 delivery-suite 的 gh_push.py
    fb = os.path.join(os.path.dirname(os.path.dirname(here)), 'delivery-suite', 'scripts', 'gh_push.py')
    if os.path.exists(fb):
        return fb
    sys.exit('找不到 gh_push.py：请通过 --gh-push 指定，或把它放到本目录 / delivery-suite/scripts/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True, help='OWNER/REPO')
    ap.add_argument('--root', required=True, help='本地仓库根目录')
    ap.add_argument('--anno', required=True, help='导出的批注 JSON（.anno.json）')
    ap.add_argument('--html', required=True, help='源 HTML 文件名')
    ap.add_argument('--message', default='同步原型批注')
    ap.add_argument('--gh-push', default=None, help='gh_push.py 路径（默认本目录或 delivery-suite）')
    args = ap.parse_args()

    anno_path = args.anno if os.path.isabs(args.anno) else os.path.join(args.root, args.anno)
    arr = json.load(open(anno_path, encoding='utf-8'))
    if not isinstance(arr, list):
        sys.exit('anno json 必须是数组')
    clean = [{k: a[k] for k in KEEP if k in a} for a in arr]

    html_path = args.html if os.path.isabs(args.html) else os.path.join(args.root, args.html)
    html = open(html_path, encoding='utf-8').read()
    new_seed = '<script id="__anno_seed" type="application/json">' + json.dumps(clean, ensure_ascii=False) + '</script>'
    html2, n = re.subn(r'<script id="__anno_seed" type="application/json">.*?</script>', new_seed, html, count=1, flags=re.S)
    if n != 1:
        sys.exit('未找到/找到多个 __anno_seed，替换失败（n=%d）' % n)
    open(html_path, 'w', encoding='utf-8').write(html2)
    print('已写回 %d 条批注到 %s' % (len(clean), args.html))

    gh_push = resolve_gh_push(args.gh_push)
    remote = os.path.basename(html_path)
    cmd = [sys.executable, gh_push, '--repo', args.repo, '--root', args.root,
           '--put', html_path + '::' + remote + '::' + args.message,
           '--wait-pages', '--live-grep', remote + '::__anno_seed']
    print('推送:', ' '.join(cmd))
    r = subprocess.run(cmd)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
