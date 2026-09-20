#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch-annotate · 写回 __anno_seed 脚本

把 annos.json 里的批注合并写回原型 HTML 的 <script id="__anno_seed">。
- 自动读现有 seed（追加模式，no 续号），不覆盖历史批注
- 校验每条 key 在 HTML 里有对应 data-anno="key" 锚点，缺失则报错退出
- sel 统一写成 [data-anno="key"]（引擎 anchorOf 规则①，改版不漂）

用法:
  python apply_annos.py --html proto.html --annos annos.json
  python apply_annos.py --html proto.html --annos annos.json --force   # 忽略现有 seed，覆盖式写入

annos.json 格式:
  [{"key":"k1","view":"viewDetail","text":"功能实现：调用 POST /api/order/save"},
   {"key":"k1","view":"viewDetail","text":"可编辑"},      # 同 key 多条 => 合并为计数角标
   {"key":"k2","view":"global","text":"选择项：固定选项：男/女"}]
"""
import argparse
import json
import re
import sys
import time
import uuid

SEED_RE = re.compile(r'<script[^>]*id="__anno_seed"[^>]*>.*?</script>', re.S | re.I)
ENGINE_RE = re.compile(r'<script[^>]*id="__anno_engine"', re.I)


def read_existing_seed(html):
    m = SEED_RE.search(html)
    if not m:
        return []
    try:
        return json.loads(m.group(0).split('>', 1)[1].rsplit('</', 1)[0])
    except Exception:
        return []


def write_seed(html, seed):
    arr = json.dumps(seed, ensure_ascii=False, indent=0)
    new_script = '<script id="__anno_seed" type="application/json">' + arr + '</script>'
    m = SEED_RE.search(html)
    if m:
        return html[:m.start()] + new_script + html[m.end():]
    idx = html.rfind('</body>')
    if idx == -1:
        idx = len(html)
    return html[:idx] + '\n' + new_script + '\n' + html[idx:]


def has_anchor(html, key):
    return ('data-anno="%s"' % key) in html or ("data-anno='%s'" % key) in html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True, help='原型 HTML 路径')
    ap.add_argument('--annos', required=True, help='annos.json 路径')
    ap.add_argument('--force', action='store_true', help='忽略现有 seed，覆盖式写入（默认追加）')
    args = ap.parse_args()

    with open(args.html, encoding='utf-8') as f:
        html = f.read()
    with open(args.annos, encoding='utf-8') as f:
        annos = json.load(f)

    if not ENGINE_RE.search(html):
        sys.stderr.write('[warn] HTML 里未检测到 __anno_engine，角标不会渲染；请先跑 '
                         'proto-annotation/scripts/inject_anno.py --html <proto.html>\n')

    existing = [] if args.force else read_existing_seed(html)

    # 校验锚点
    missing = sorted({a['key'] for a in annos if not has_anchor(html, a['key'])})
    if missing:
        sys.stderr.write('ERROR: 以下 data-anno 锚点在 HTML 中找不到，请先用 Edit 加上：%s\n' % missing)
        sys.exit(2)

    max_no = max([a.get('no', 0) for a in existing] + [0])
    seed = list(existing) if not args.force else []
    for a in annos:
        max_no += 1
        seed.append({
            'id': a.get('id') or ('a' + uuid.uuid4().hex[:12]),
            'no': a.get('no') or max_no,
            'view': a.get('view', 'global'),
            'sel': '[data-anno="%s"]' % a['key'],
            'text': a['text'],
            'ts': a.get('ts') or int(time.time() * 1000),
            'valid': True,
        })

    out = write_seed(html, seed)
    with open(args.html, 'w', encoding='utf-8') as f:
        f.write(out)

    print('OK: 写入 %d 条（原 %d + 新 %d），总计 %d；视图分布: %s' % (
        len(annos), len(existing), len(annos), len(seed),
        {v: sum(1 for s in seed if s['view'] == v) for v in sorted({s['view'] for s in seed})}))


if __name__ == '__main__':
    main()
