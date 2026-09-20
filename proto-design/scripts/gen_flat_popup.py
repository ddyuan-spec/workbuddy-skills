#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_flat_popup.py — 把原型里某个弹窗/屏幕单独生成「平铺设计稿」（单页，带一键复制，可粘墨刀）

支持同一节点生成多个「内容变体」（如 空态/有值、登录前/登录后），每份独立 HTML + 一键复制。

用法：
  python gen_flat_popup.py --source task-entry-prototype.html --selector "#powerRecordModal" \
      --output-dir ./out --title "虎力值变动记录弹窗"

变体在脚本内 VARIANTS 字典定义（键=文件名前缀，值=该变体的内容补丁函数）。
适配任意弹窗：改 VARIANTS 即可；selector 指定要抽取的节点。

复制按钮复制 .pf-board（含全部样式，不含工具栏），粘墨刀即显示。
"""
import os
import argparse
from bs4 import BeautifulSoup

# ===== 平铺修复 CSS（与 gen_flat_modao.py 同源，5 层展开规则）=====
FLAT_CSS = """
*{box-sizing:border-box;}
body{display:block !important;width:100%;min-height:100vh;background:#eef0f4;margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}
.copy-bar{position:sticky;top:0;left:0;z-index:100;background:#1a1a2e;color:#fff;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,.25);width:100%;box-sizing:border-box;}
.copy-bar .t{font-size:15px;font-weight:700;}
.copy-bar .i{font-size:12px;color:#a6adc8;margin-top:2px;}
.copy-btn{padding:9px 22px;border:none;border-radius:22px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font-size:14px;font-weight:700;cursor:pointer;flex-shrink:0;}
.copy-btn.copied{background:linear-gradient(135deg,#059669,#047857);}
.pf-board{display:flex;gap:40px;flex-wrap:nowrap;overflow-x:auto;padding:40px 30px 100px;align-items:flex-start;background:#eef0f4;}
.pf-col{display:flex;flex-direction:column;align-items:center;flex:0 0 auto;}
.pf-label{font-size:14px;font-weight:600;color:#333;background:#fff;padding:6px 16px;border-radius:20px;box-shadow:0 2px 6px rgba(0,0,0,.1);margin-bottom:14px;white-space:nowrap;}
.pf-phone{flex:0 0 375px;width:375px;height:auto;min-height:800px;background:#f5f5f5;border-radius:40px;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);overflow:hidden;position:relative;display:flex;flex-direction:column;}
.pf-statusbar{height:44px;background:#1a1a2e;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 22px;font-size:13px;flex-shrink:0;}
.pf-content{position:relative;flex:1;min-height:756px;height:auto;overflow:visible;}
.pf-content .screen,.pf-content .sub-screen,.pf-content .ob-step{position:relative !important;inset:auto !important;display:block !important;height:auto !important;min-height:0 !important;max-height:none !important;width:100% !important;overflow:visible !important;z-index:auto !important;}
.pf-content .ob-body,.pf-content .ob-body.open{max-height:none !important;overflow:visible !important;}
.pf-content [style*="display:none"]{display:block !important;}
.pf-content .inputbar,.pf-content .ob-footer,.pf-content .cp-footer,.pf-content .ck-footer{position:static !important;left:auto !important;right:auto !important;top:auto !important;bottom:auto !important;width:100% !important;}
.pf-content .modal-overlay,.pf-content .float-input-overlay,.pf-content .modal{position:absolute !important;inset:0 !important;display:flex !important;align-items:center;justify-content:center;background:rgba(0,0,0,.45) !important;height:100% !important;width:100% !important;overflow:hidden !important;z-index:50 !important;}
.pf-content .modal .box,.pf-content .modal-box{background:#fff;border-radius:18px;width:300px;padding:24px 20px;text-align:center;max-height:none !important;overflow:visible !important;}
.copy-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,.25);opacity:0;transition:opacity .3s;pointer-events:none;z-index:200;}
.copy-toast.show{opacity:1;}
"""

SCRIPT_JS = """
<script>
function showCopyToast(msg){
  var t=document.getElementById('copyToast');
  if(!t){t=document.createElement('div');t.id='copyToast';t.className='copy-toast';document.body.appendChild(t);}
  t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show');},1800);
}
function doCopy(){
  var css=document.querySelector('style').textContent;
  var board=document.getElementById('board').outerHTML;
  var src='<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>'+css+'</style></head><body>'+board+'</body></html>';
  navigator.clipboard.writeText(src).then(function(){
    var b=document.getElementById('copyBtn');b.textContent='✓ 已复制';b.classList.add('copied');
    showCopyToast('已复制干净源码，可直接粘贴到墨刀');
    setTimeout(function(){b.textContent='一键复制源码';b.classList.remove('copied');},1800);
  }).catch(function(){alert('复制失败，请手动选择复制');});
}
</script>
"""

# ===== 本需求预置：虎力值变动记录弹窗 · 有值 / 无值 两种变体 =====
EMPTY_HTML = '<div class="pr-page-empty"><div class="pei">📋</div>暂无虎力值变动记录</div>'

FILLED_HTML = """<div class="pr-page-item"><div class="pr-page-info"><div class="pr-page-title">完成「每日 AI 对话」任务</div><div class="pr-page-time">2026-07-14 10:32</div></div><div class="pr-page-val plus">+5</div></div>
<div class="pr-page-item"><div class="pr-page-info"><div class="pr-page-title">完成「每日打卡」任务</div><div class="pr-page-time">2026-07-13 21:15</div></div><div class="pr-page-val plus">+2</div></div>
<div class="pr-page-item"><div class="pr-page-info"><div class="pr-page-title">分享泰小虎给好友</div><div class="pr-page-time">2026-07-13 18:40</div></div><div class="pr-page-val plus">+3</div></div>
<div class="pr-page-item"><div class="pr-page-info"><div class="pr-page-title">完善健康档案（性别/出生日期）</div><div class="pr-page-time">2026-07-12 09:05</div></div><div class="pr-page-val plus">+10</div></div>"""

def patch_list(html, content):
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('#powerRecordList')
    if box is not None:
        box.clear()
        box.append(BeautifulSoup(content, 'html.parser'))
    return str(soup)

# 键=文件名前缀，值=(标签, 内容补丁函数)
VARIANTS = {
    'power-record-filled': ('虎力值变动记录·有值', lambda h: patch_list(h, FILLED_HTML)),
    'power-record-empty':  ('虎力值变动记录·无值', lambda h: patch_list(h, EMPTY_HTML)),
}


def render(title, css, board_html):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<div class="copy-bar">
  <div>
    <div class="t">📋 {title}</div>
    <div class="i">单页平铺 · 无交互 · 一键复制源码粘墨刀</div>
  </div>
  <button class="copy-btn" id="copyBtn" onclick="doCopy()" title="点击复制完整 HTML 源码，粘贴到墨刀">一键复制源码</button>
</div>
<div class="copy-toast" id="copyToast">已复制干净源码，可直接粘贴到墨刀</div>
<div class="pf-board" id="board">
{board_html}
</div>
{SCRIPT_JS}
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='原型 HTML 路径')
    ap.add_argument('--selector', default='#s-powerrecord', help='要平铺的节点 CSS 选择器')
    ap.add_argument('--output-dir', default='.', help='输出目录')
    ap.add_argument('--title', default='虎力值变动记录页', help='标题前缀')
    args = ap.parse_args()

    with open(args.source, encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    style_tag = soup.find('style')
    base_css = style_tag.get_text() if style_tag else ''

    el = soup.select_one(args.selector)
    if not el:
        raise SystemExit(f'[error] 未找到节点 {args.selector}')
    base = str(el)

    os.makedirs(args.output_dir, exist_ok=True)
    for key, (label, patch) in VARIANTS.items():
        snippet = patch(base)
        board = (f'<div class="pf-col"><div class="pf-label">{label}</div>'
                 f'<div class="pf-phone"><div class="pf-statusbar"><span>9:41</span>'
                 f'<span>📶 📡 🔋</span></div>'
                 f'<div class="pf-content">{snippet}</div></div></div>')
        title = f'{args.title} · {label}'
        out = render(title, base_css + FLAT_CSS, board)
        path = os.path.join(args.output_dir, f'{key}.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(out)
        print(f'[ok] {path}')


if __name__ == '__main__':
    main()
