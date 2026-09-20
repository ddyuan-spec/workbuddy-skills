#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批注层回归验证（真实页面 + 无头 Edge）。改完 assets/engine.js|css 并 inject 之后跑这个。

验证四件事：
  1. 定位：用页面里引擎**自己的 cssPath** 造真实选择器，喂回引擎，角标必须贴在「被点的那个小元素」上，
     不许被甩到整行/整卡的最右端（2026-09-17 的「定位到大模块」事故）。
  2. 合并：同一元素多条 → 合成 1 个橙色计数角标。
  3. 删除：合并面板必须能逐条删（桩掉 confirm 后点「删除」），本地存储 4→3→2→1，面板自动重开，剩 1 条回落普通角标。
  4. 健康：工具栏 7 个按钮齐全、无运行期报错。

用法:
  python verify_anno.py --html path/to/proto.html
  python verify_anno.py --html path/to/proto.html --view viewDetail \
      --target '#viewDetail input[value="水卡"]' --expect-tag LABEL

退出码 0 = 全过；1 = 有断言失败（详情打在 stdout）。
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/microsoft-edge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("找不到 Edge，请用 --edge 指定路径")


def extract_csspath(html):
    """从目标页面自己的 __anno_engine 里抽真实 cssPath 源码（保证测的就是线上那份算法）。"""
    m = re.search(r'<script id="__anno_engine">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("目标 HTML 里没有 __anno_engine，请先注入批注引擎")
    eng = m.group(1)
    m2 = re.search(r"function cssPath\(el\)\{[\s\S]*?\n  \}", eng)
    if not m2:
        sys.exit("引擎里找不到 cssPath，可能已被改写——请同步更新本脚本")
    return m2.group(0), eng


def build_page(html, csspath_src, view, target):
    view_js = ""
    if view:
        view_js = ("var _v=document.getElementById(%r);"
                   "if(_v){document.querySelectorAll('.view,.page').forEach(function(x){x.classList.remove('active');});"
                   "_v.classList.add('active');}" % view)
    probe = """
<script>
(function(){
  window.confirm=function(){ window.__cc=(window.__cc||0)+1; return true; };   /* 无头下自动确认 */
  %s
  %s
  var el = document.querySelector(%r);
  if(!el){ window.__T={err:'target not found'}; return; }
  window.__T={t:el};
  var list = document.querySelectorAll(%r);
  var el2 = (list.length>1) ? list[1] : null;   /* 第二个目标：验证不同元素各自成角标、不串 */  function mk(id,no,e,t){ return {id:id,no:no,view:'',sel:cssPath(e),text:t,ts:Date.now()}; }
  var a=[]; for(var i=1;i<=4;i++) a.push(mk('m'+i,i,el,'第'+i+'条 合并删除用'));
  if (el2) a.push(mk('o1',9,el2,'另一个元素的批注'));
  window.__T.total = a.length; window.__T.n = a.length - (el2?1:0);
  document.getElementById('__anno_seed').textContent=JSON.stringify(a);
})();
</script>
""" % (view_js, csspath_src, target, target)
    # 视图名：引擎按 .view.active 的 id 判定，这里让引擎自己算，seed 里 view 留空则视为 global（不隔离）
    reporter = """
<pre id="out">running</pre>
<script>
setTimeout(function(){
  function R(e){var r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)];}
  var key='__anno__'+location.pathname.split('/').pop();
  var out={steps:[],toolbar:0};
  ['批注','隐藏','列表','导出','导入','同步','清空'].forEach(function(b){
    var hit=false; document.querySelectorAll('.__anno-tb button').forEach(function(x){ if(x.textContent===b) hit=true; });
    if(hit) out.toolbar++;
  });
  out.target = window.__T && window.__T.t ? R(window.__T.t) : null;
  out.total = (window.__T && window.__T.total) || 0;
  out.n = (window.__T && window.__T.n) || 0;
  function snap(tag){
    out.steps.push({tag:tag,
      flags:document.querySelectorAll('.__anno-flag').length,
      flagText:[].map.call(document.querySelectorAll('.__anno-flag'),function(f){return f.textContent;}).join(','),
      items:document.querySelectorAll('.__anno-bubble .m-item').length,
      delBtns:document.querySelectorAll('.__anno-bubble .m-del').length,
      stored:JSON.parse(localStorage.getItem(key)||'[]').length,
      flags2:[].map.call(document.querySelectorAll('.__anno-flag'),function(f){var p=f.parentElement;
        return {text:f.textContent,multi:f.getAttribute('data-multi')||'-',pos:f.getAttribute('data-pos')||'corner',
                parent:(p.tagName||'')+'.'+String(p.className||'').split(/\\s+/).join('.'),rect:R(f)};})});
  }
  var mf=document.querySelector('.__anno-flag[data-multi="1"]');
  if(mf){ mf.dispatchEvent(new MouseEvent('click',{bubbles:true})); snap('打开合并面板');
    for(var k=0;k<3;k++){ var d=document.querySelector('.__anno-bubble .m-del'); if(!d) break;
      d.dispatchEvent(new MouseEvent('click',{bubbles:true})); snap('删第'+(k+1)+'条'); }
  } else { snap('无合并角标'); }
  var f=document.querySelector('.__anno-flag');
  if(f){ f.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    out.lastBtns=[].map.call(document.querySelectorAll('.__anno-bubble .b-actions button'),function(b){return b.textContent;});
    out.singleParent=(f.parentElement.tagName||'')+'.'+String(f.parentElement.className||'').split(/\\s+/).join('.');
    out.singleMulti=f.getAttribute('data-multi')||'-';
  }
  document.getElementById('out').textContent=btoa(unescape(encodeURIComponent(JSON.stringify(out))));
},700);
</script>
"""
    h = html.replace('<script id="__anno_engine">', probe + '\n<script id="__anno_engine">', 1)
    # 探针/reporter 注入到【最后一个】</body> 前（避免命中 JS 字符串里的 </body>，如 C 端 __protoBuildStandalone）
    # 注意：last 必须从 h（已含 probe 插入）里算，否则偏移错位会把 reporter 插进脚本里导致不执行
    last = None
    for mm in re.finditer(r'</body>', h, re.I):
        last = mm
    if last is not None:
        h = h[:last.start()] + reporter + h[last.start():]
    else:
        h = h + '\n' + reporter
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--view', default='', help='要激活的视图 id（如 viewDetail）；留空则用页面默认视图')
    ap.add_argument('--target', default='', help='要批注的目标 CSS 选择器；默认自动挑第一个单选项/输入框')
    ap.add_argument('--expect-tag', default='', help='断言角标父元素应包含的标签名，如 LABEL')
    ap.add_argument('--edge', default='')
    args = ap.parse_args()

    edge = args.edge or find_edge()
    html = open(args.html, encoding='utf-8').read()
    csspath_src, _ = extract_csspath(html)

    if not args.target:
        args.target = 'input[type=radio]'   # 探针内有完整兜底链，找不到会自动换 input/button/label/li
    page = build_page(html, csspath_src, args.view, args.target)
    tmp = os.path.join(tempfile.gettempdir(), 'anno_verify.html')
    open(tmp, 'w', encoding='utf-8').write(page)

    dump = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox',
                           '--virtual-time-budget=4000', '--dump-dom',
                           'file:///' + tmp.replace('\\', '/')],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8', 'ignore')
    m = re.search(r'<pre id="out">([^<]*)</pre>', dump)
    if not m or m.group(1) == 'running':
        print('探针未执行（页面可能报错或被 CSP 拦住）；dump 大小 %d' % len(dump))
        sys.exit(1)
    out = json.loads(base64.b64decode(m.group(1)).decode('utf-8'))
    if out.get('target') is None:
        print('目标元素没找到，无法验证。请用 --target 指定一个页面里真实存在的选择器')
        print('  （提示：C 端手机模型常需要 --view p_xxx 先激活某个 .page，再 --target 指向里面的元素）')
        sys.exit(2)

    print('目标元素矩形 [l,t,r,b]:', out.get('target'))
    print('工具栏按钮: %d/7' % out['toolbar'])
    print('%-14s %-5s %-8s %-8s %-8s %s' % ('步骤', '角标数', '角标文字', '面板条目', '删除按钮', '本地存储'))
    for s in out['steps']:
        print('%-14s %-7s %-10s %-10s %-10s %s' % (s['tag'], s['flags'], s['flagText'], s['items'], s['delBtns'], s['stored']))
    for s in out['steps'][:1]:
        for f in s.get('flags2', []):
            print('   角标 %s multi=%s pos=%s parent=%s rect=%s' % (f['text'], f['multi'], f['pos'], f['parent'], f['rect']))

    fails = []
    if out['toolbar'] != 7:
        fails.append('工具栏按钮不全: %d/7' % out['toolbar'])
    steps = out['steps']
    n_group = out.get('n') or 4
    if not steps or steps[0]['tag'] != '打开合并面板':
        fails.append('同一元素的 %d 条批注没有合并成 1 个计数角标' % n_group)
    else:
        multi = [x for x in steps[0]['flags2'] if x['multi'] == '1']
        if len(multi) != 1:
            fails.append('合并角标应恰好 1 个，实际 %d' % len(multi))
        else:
            f0 = multi[0]
            tgt = out['target']
            if tgt:
                dx = abs(f0['rect'][0] - tgt[2]); dy = abs(f0['rect'][1] - tgt[1])
                if dx > 120 or dy > 120:
                    fails.append('角标没贴在目标元素上（距目标 %d,%d px）→ 疑似又跳到大容器' % (dx, dy))
            if args.expect_tag and args.expect_tag.upper() not in f0['parent'].upper():
                fails.append('角标父元素应为 %s，实际 %s' % (args.expect_tag, f0['parent']))
            if f0['text'] != str(n_group):
                fails.append('合并角标应显示条数 %d，实际 %s' % (n_group, f0['text']))
        if steps[0]['delBtns'] != n_group:
            fails.append('合并面板应有 %d 个逐条删除按钮，实际 %d' % (n_group, steps[0]['delBtns']))
        if steps[0]['items'] != n_group:
            fails.append('合并面板条目应为 %d，实际 %d' % (n_group, steps[0]['items']))
    # 逐条删除：面板条目递减、本地存储严格 -1
    for i in range(1, min(4, len(steps))):
        want = n_group - i
        if want > 1 and steps[i]['items'] != want:
            fails.append('删 %d 条后面板应剩 %d 条，实际 %d' % (i, want, steps[i]['items']))
        if want == 1 and steps[i]['items'] != 0:
            fails.append('只剩 1 条时面板应关闭，实际还有 %d 条' % steps[i]['items'])
        exp_store = out.get('total', n_group) - i
        if steps[i]['stored'] != exp_store:
            fails.append('删 %d 条后本地存储应为 %d，实际 %d' % (i, exp_store, steps[i]['stored']))
    if len(steps) >= 4:
        last = steps[3]['flags2']
        if [x for x in last if x['multi'] == '1']:
            fails.append('删到剩 1 条时不应还是合并角标')
        if out.get('singleMulti') != '-':
            fails.append('末态角标的 multi 标记应为空，实际 %s' % out.get('singleMulti'))
    if '删除' not in str(out.get('lastBtns')):
        fails.append('单条气泡缺「删除」按钮：%s' % out.get('lastBtns'))

    print()
    if fails:
        print('FAIL:')
        for x in fails:
            print('  -', x)
        sys.exit(1)
    print('PASS: 角标贴目标 / 同元素合并 / 逐条删除(4→3→2→1) / 单条气泡含删除 / 工具栏齐')


if __name__ == '__main__':
    main()
