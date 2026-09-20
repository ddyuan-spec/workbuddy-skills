#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实浏览器回归校验 proto-annotation 引擎（headless Edge，非预激活）。

校验四态，全部基于「全新 profile + --dump-dom」读真实失联态，杜绝预激活骗过校验：
  态A 默认(弹窗关)：角标总数 == seed 数（全量），无失联；关着的弹窗内字段落 pending 堆右上角。
  态B 开弹窗：只显示弹窗内字段角标，背景字段隐藏（不穿透）。
  态C 多弹窗(顶层覆盖)：上层弹窗 z 更高且无字段 → 0 角标（下层弹窗角标不穿透到顶层）。
  态C2 多弹窗(下层被盖)：下层弹窗 z 更低 → 仍只显示顶层弹窗内字段。

用法：
  python verify_real.py                        # 校验内置 sample_proto.html
  python verify_real.py --html 你的原型.html    # 校验任意已注入引擎+seed 的原型
  python verify_real.py --edge "C:/path/msedge.exe"
"""
import argparse, html, json, os, re, shutil, subprocess, sys, tempfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, 'sample_proto.html')
INJECT = os.path.join(HERE, 'inject_anno.py')
EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
MODAL_CLASSES = {'cf-mask', 'cf-modal', 'wct-mask', 'wct-modal', 'mask', 'modal',
                 'dialog', 'overlay', 'popup'}


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which('msedge')


class AnnoParser(HTMLParser):
    """收集所有 data-anno 元素，并判定其是否处于某弹窗容器内（祖先含 modal class）。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.class_stack = []
        self.in_modal = set()

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        classes = set((d.get('class') or '').split())
        self.class_stack.append(classes)
        if 'data-anno' in d:
            if any(MODAL_CLASSES & cs for cs in self.class_stack):
                self.in_modal.add(d['data-anno'])

    def handle_endtag(self, tag):
        if self.class_stack:
            self.class_stack.pop()


def parse_anno_ids(html_text):
    p = AnnoParser()
    p.feed(html_text)
    return p.in_modal


def read_seed(html_text):
    m = re.search(r'<script id="__anno_seed"[^>]*>(.*?)</script>', html_text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:
        return []


def dump_dom(edge, path):
    ud = tempfile.mkdtemp()
    url = 'file:///' + path.replace('\\', '/')
    try:
        r = subprocess.run(
            [edge, '--headless', '--disable-gpu', '--no-sandbox',
             '--user-data-dir=' + ud, '--virtual-time-budget=8000', '--dump-dom', url],
            capture_output=True, text=True, timeout=180)
    finally:
        shutil.rmtree(ud, ignore_errors=True)
    return r.stdout


def parse_flags(dom):
    ok, pending, lost = set(), set(), set()
    multi = 0
    for cls, attrs, no in re.findall(r'<div class="__anno-flag([^"]*)"([^>]*?)>(\d+)</div>', dom):
        if 'data-multi' in cls:
            multi += 1
            continue
        try:
            n = int(no)
        except Exception:
            continue
        if 'data-missing' in attrs:
            lost.add(n)
        elif 'data-pending' in attrs:
            pending.add(n)
        else:
            ok.add(n)
    return ok, pending, lost, multi


def build_injected(edge, base_html, mutate=None):
    """从 base_html（已含 __anno_seed 的原型文本）构造一个临时文件：
       1) 可选 mutate() 预修改 DOM（如打开弹窗 / 插入顶层覆盖弹窗，必须在注入引擎前完成）；
       2) 注入引擎（保留 seed）；
       3) dump-dom 返回真实失联态。
       避免「引擎注入后才插 wctMask2 → init render 时它尚不存在」的构造陷阱。"""
    h = base_html
    if mutate:
        h = mutate(h)
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8').name
    open(tmp, 'w', encoding='utf-8').write(h)
    inj = subprocess.run([sys.executable, INJECT, '--html', tmp, '--force'],
                         capture_output=True, text=True)
    if inj.returncode != 0:
        sys.exit('注入引擎失败: ' + inj.stderr)
    dom = dump_dom(edge, tmp)
    try:
        os.remove(tmp)
    except Exception:
        pass
    return dom


def open_wctmask(h):
    return h.replace('id="wctMask"', 'id="wctMask" style="display:flex"', 1)


def add_cover_modal(h, z):
    return h.replace('</body>',
                     '<div id="wctMask2" class="wct-mask" style="display:flex;z-index:%d">'
                     '<div class="wct-modal">覆盖层测试</div></div></body>' % z, 1)


def main():
    ap = argparse.ArgumentParser(description='proto-annotation 真实浏览器回归校验')
    ap.add_argument('--html', default=SAMPLE, help='已含 __anno_seed 的原型 HTML（会先注入引擎再校验）')
    ap.add_argument('--edge', default=None)
    args = ap.parse_args()

    edge = args.edge or find_edge()
    if not edge or not os.path.exists(edge):
        sys.exit('未找到 Edge，请用 --edge 指定路径')

    html0 = open(args.html, encoding='utf-8').read()
    data = read_seed(html0)
    if not data:
        sys.exit('未找到 __anno_seed，无法校验全量')
    total = len(data)
    modal_ids = parse_anno_ids(html0)
    modal_nos = set(a['no'] for a in data if a.get('id') in modal_ids)
    print('seed 总数: %d | 弹窗内字段 no: %s' % (total, sorted(modal_nos)))

    fails = []

    # 态A 默认（弹窗关）：全量 19，关着的弹窗内字段落 pending 堆右上角
    domA = build_injected(edge, html0)
    okA, pendA, lostA, _ = parse_flags(domA)
    print('态A 默认(弹窗关): ok=%s pending=%s lost=%s' % (sorted(okA), sorted(pendA), sorted(lostA)))
    if lostA:
        fails.append('态A 有失联: %s' % sorted(lostA))
    if len(okA) + len(pendA) != total:
        fails.append('态A 全量不符: ok+pend=%d != %d' % (len(okA) + len(pendA), total))
    if pendA != modal_nos:
        fails.append('态A pending 应为弹窗内字段 %s, 实际 %s' % (sorted(modal_nos), sorted(pendA)))

    # 态B 开弹窗（强制 display:flex）：只显示弹窗内字段，背景隐藏、无 pending
    domB = build_injected(edge, html0, open_wctmask)
    okB, pendB, lostB, _ = parse_flags(domB)
    print('态B 开弹窗: ok=%s pending=%s lost=%s' % (sorted(okB), sorted(pendB), sorted(lostB)))
    if lostB:
        fails.append('态B 有失联: %s' % sorted(lostB))
    if okB != modal_nos:
        fails.append('态B ok 应只弹窗内 %s, 实际 %s' % (sorted(modal_nos), sorted(okB)))
    if pendB:
        fails.append('态B 不应有 pending: %s' % sorted(pendB))

    # 态C 多弹窗（顶层覆盖，z=9999 且无字段）：上层覆盖 → 0 角标（下层弹窗不穿透）
    domC = build_injected(edge, html0, lambda h: add_cover_modal(open_wctmask(h), 9999))
    okC, _, _, _ = parse_flags(domC)
    print('态C 多弹窗(顶层覆盖): ok=%s' % sorted(okC))
    if okC:
        fails.append('态C 顶层覆盖应 0 角标(穿透0), 实际 %s' % sorted(okC))

    # 态C2 多弹窗（下层被盖，z=1000）：下层 → 仍只显示顶层(wctMask)内字段
    domC2 = build_injected(edge, html0, lambda h: add_cover_modal(open_wctmask(h), 1000))
    okC2, _, _, _ = parse_flags(domC2)
    print('态C2 多弹窗(下层被盖): ok=%s' % sorted(okC2))
    if okC2 != modal_nos:
        fails.append('态C2 应只显示顶层(wctMask)内 %s, 实际 %s' % (sorted(modal_nos), sorted(okC2)))

    if fails:
        print('\n❌ 校验失败:')
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('\n✅ ALL PASS：默认全量 + 弹窗隔离 + 多弹窗顶层隔离 全部通过')


if __name__ == '__main__':
    main()
