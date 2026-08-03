#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_flat_modao.py — 把交互式 HTML 原型转成「平铺设计稿」（给墨刀用）

用法：
  python gen_flat_modao.py
  python gen_flat_modao.py --source task-entry-prototype.html --output task-entry-flat.html --title "泰小虎·客户端任务入口—平铺设计稿（墨刀用）"

产出：一个横向平铺、每状态一个手机框、无交互、带「一键复制干净源码」按钮的 HTML。
复制按钮复制的是 .pf-board 的完整源码（含全部样式，不含顶部工具栏），直接粘墨刀即显示全部状态。

适配任意原型：
  - 改 SOURCE 指向原型（或 --source）
  - 改 NODES 清单列出要平铺的节点（CSS选择器, 标签, 描述）
  - 改 PATCHES 对靠 JS 动态生成的节点做静态补值
"""
import os
import argparse
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'task-entry-prototype.html')
OUTPUT = os.path.join(HERE, 'task-entry-flat.html')
TITLE  = '泰小虎 · 客户端任务入口 — 平铺设计稿（墨刀用）'

# 要平铺的节点清单：(CSS选择器, 标签, 描述)
NODES = [
    ('#s-home', '首页·AI会话', '三个问题行入口 + 对话窗'),
    ('#s-profile', '健康档案', '体型/体征/睡眠/就医 + 任务'),
    ('#s-service', '服务', 'Banner 轮播 + 健康好物'),
    ('#s-mine', '我的', '资产/等级/订单/对话记录'),
    ('#s-task', '健康任务', '任务列表页（6个任务）'),
    ('#s-bodydata', '体型数据录入', '体重/身高/BMI'),
    ('#s-createplan', '创建计划', '名称+描述+提醒'),
    ('#s-onboarding', '建档引导·整体', '显示第1步（性别）'),
    ('#obs0', '引导·性别', '男/女选择'),
    ('#obs1', '引导·出生日期', '年/月/日滚轮（已补示例值）'),
    ('#obs2', '引导·身高', '滑块 140-200cm'),
    ('#obs3', '引导·体重BMI', '滑块 + BMI 结果'),
    ('#s-checkin', '打卡记录', '30天进度 + 感受 + 图片'),
    ('#s-levelreport', '等级报告', '注册/连续登录/等级/加速'),
    ('#s-share', '分享泰小虎', '海报 + 4 种分享方式'),
    ('#floatOverlay', '浮层输入框', '输入体重/身高'),
    ('#modal', '打卡成功提示', '轻提示弹窗'),
    ('#s-powerrecord', '虎力值变动记录', '整页明细（空态含提示）'),
]

# ---- 针对特定节点的内容补丁（源里靠 JS 动态生成，平铺时需静态补值）----
def patch_obs1(html):
    years  = ''.join(f'<div class="wheel-item" style="padding:8px 0;text-align:center;font-size:16px;color:#333">{y}</div>' for y in range(2006, 1995, -1))
    months = ''.join(f'<div class="wheel-item" style="padding:8px 0;text-align:center;font-size:16px;color:#333">{m:02d}</div>' for m in range(1, 13))
    days   = ''.join(f'<div class="wheel-item" style="padding:8px 0;text-align:center;font-size:16px;color:#333">{d:02d}</div>' for d in range(1, 32))
    html = html.replace('<div class="wheel-col" id="wheelYear"></div>', f'<div class="wheel-col" id="wheelYear">{years}</div>')
    html = html.replace('<div class="wheel-col" id="wheelMonth"></div>', f'<div class="wheel-col" id="wheelMonth">{months}</div>')
    html = html.replace('<div class="wheel-col" id="wheelDay"></div>', f'<div class="wheel-col" id="wheelDay">{days}</div>')
    return html

def patch_s_onboarding(html):
    """s-onboarding 整体只保留第一步（obs0），其余步骤隐藏"""
    soup = BeautifulSoup(html, 'html.parser')
    for step in soup.select('.ob-step'):
        if step.get('id') != 'obs0':
            step.decompose()
        else:
            cls = step.get('class', [])
            if 'force-show' not in cls:
                cls.append('force-show')
                step['class'] = cls
    return str(soup)

def patch_power_record(html):
    """虎力值变动记录页：JS 未跑时列表为空且无提示，静态补入空态提示文案"""
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('#powerRecordList')
    if box is not None and not box.get_text(strip=True):
        box.clear()
        box.append(BeautifulSoup('<div class="pr-page-empty"><div class="pei">📋</div>暂无虎力值变动记录</div>', 'html.parser'))
    return str(soup)

PATCHES = {
    'obs1': patch_obs1,
    's-onboarding': patch_s_onboarding,
    's-powerrecord': patch_power_record,
}

FLAT_CSS = """
/* ===== 平铺修复：把交互原型的所有屏幕/弹窗/折叠层在独立手机框里全部展开 ===== */
*{box-sizing:border-box;}
/* 覆盖原型的 body flex 布局，避免工具栏被挤到左侧 */
body{display:block !important;width:100%;min-height:100vh;background:#eef0f4;}
/* 顶部复制工具栏 */
.copy-bar{position:sticky;top:0;left:0;z-index:100;background:#1a1a2e;color:#fff;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,.25);width:100%;box-sizing:border-box;}
.copy-bar .t{font-size:15px;font-weight:700;}
.copy-bar .i{font-size:12px;color:#a6adc8;margin-top:2px;}
.copy-btn{padding:9px 22px;border:none;border-radius:22px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font-size:14px;font-weight:700;cursor:pointer;flex-shrink:0;transition:transform .1s,box-shadow .2s;}
.copy-btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(124,58,237,.35);}
.copy-btn.copied{background:linear-gradient(135deg,#059669,#047857);}
/* 平铺画板 */
.pf-board{display:flex;gap:40px;flex-wrap:nowrap;overflow-x:auto;padding:40px 30px 100px;align-items:flex-start;background:#eef0f4;}
.pf-col{display:flex;flex-direction:column;align-items:center;flex:0 0 auto;}
.pf-label{font-size:14px;font-weight:600;color:#333;background:#fff;padding:6px 16px;border-radius:20px;box-shadow:0 2px 6px rgba(0,0,0,.1);margin-bottom:14px;white-space:nowrap;}

/* 手机框：固定 375px 宽，至少 800px 高（真机视口），内容超高时整框自然增高 */
.pf-phone{flex:0 0 375px;width:375px;height:auto;min-height:800px;background:#f5f5f5;border-radius:40px;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);overflow:hidden;position:relative;display:flex;flex-direction:column;}
.pf-statusbar{height:44px;background:#1a1a2e;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 22px;font-size:13px;flex-shrink:0;}
/* 内容区：至少 800px，作为模态/浮层的定位参照；普通屏幕内容超高时整框增高 */
.pf-content{position:relative;flex:1;min-height:756px;height:auto;overflow:visible;}

/* —— 第 1 层：屏幕/子屏/引导步骤 全部强制显示、自然高度 —— */
.pf-content .screen,
.pf-content .sub-screen,
.pf-content .ob-step{
  position:relative !important;inset:auto !important;top:auto !important;left:auto !important;
  right:auto !important;bottom:auto !important;
  display:block !important;height:auto !important;min-height:0 !important;max-height:none !important;
  width:100% !important;overflow:visible !important;z-index:auto !important;
}
/* —— 第 2 层：折叠的建档引导卡片正文（.ob-body{max-height:0}）强制展开 —— */
.pf-content .ob-body,
.pf-content .ob-body.open{max-height:none !important;overflow:visible !important;}
/* —— 第 3 层：内联 style="display:none" 的面板（如 #pother 体型录入 Tab）强制显示 —— */
.pf-content [style*="display:none"]{display:block !important;}
/* —— 第 4 层：绝对定位底栏改为正常文档流，避免跑到整屏最底部 —— */
.pf-content .inputbar,
.pf-content .ob-footer,
.pf-content .cp-footer,
.pf-content .ck-footer{
  position:static !important;left:auto !important;right:auto !important;top:auto !important;
  bottom:auto !important;width:100% !important;
}
/* —— 第 5 层：模态/浮层 填满手机框并居中弹窗（独立卡片时作为 800px 视口） —— */
.pf-content .modal-overlay,
.pf-content .float-input-overlay,
.pf-content .modal{
  position:absolute !important;inset:0 !important;display:flex !important;
  align-items:center;justify-content:center;background:rgba(0,0,0,.45) !important;
  height:100% !important;width:100% !important;overflow:hidden !important;z-index:50 !important;
}
.pf-content .modal .box,
.pf-content .modal-box{background:#fff;border-radius:18px;width:300px;padding:24px 20px;text-align:center;max-height:none !important;overflow:visible !important;}

/* 建档引导·整体 卡片只保留第 1 步，其余步骤隐藏 */
#s-onboarding .ob-step:not(.force-show){display:none !important;}

/* 复制成功提示 toast */
.copy-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,.25);opacity:0;transition:opacity .3s;pointer-events:none;z-index:200;}
.copy-toast.show{opacity:1;}
"""

SCRIPT_JS = """
<script>
function showCopyToast(msg){
  var t = document.getElementById('copyToast');
  if(!t){t=document.createElement('div');t.id='copyToast';t.className='copy-toast';document.body.appendChild(t);}
  t.textContent = msg; t.classList.add('show');
  setTimeout(function(){t.classList.remove('show');},1800);
}
function doCopy(){
  var css = document.querySelector('style').textContent;
  var board = document.getElementById('board').outerHTML;
  var src = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>'+css+'</style></head><body>'+board+'</body></html>';
  navigator.clipboard.writeText(src).then(function(){
    var b=document.getElementById('copyBtn');b.textContent='✓ 已复制';b.classList.add('copied');
    showCopyToast('已复制干净源码，可直接粘贴到墨刀');
    setTimeout(function(){b.textContent='一键复制源码';b.classList.remove('copied');},1800);
  }).catch(function(){alert('复制失败，请手动选择复制');});
}
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=SOURCE)
    ap.add_argument('--output', default=OUTPUT)
    ap.add_argument('--title', default=TITLE)
    args = ap.parse_args()

    src, out_path, title = args.source, args.output, args.title

    with open(src, encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    style_tag = soup.find('style')
    base_css = style_tag.get_text() if style_tag else ''

    cards = []
    for sel, label, desc in NODES:
        el = soup.select_one(sel)
        if not el:
            print(f'[warn] 未找到节点 {sel}，跳过')
            continue
        snippet = str(el)
        nid = sel.lstrip('#.')
        if nid in PATCHES:
            snippet = PATCHES[nid](snippet)
        if nid.startswith('obs'):
            snippet = snippet.replace('class="ob-step active"', 'class="ob-step active force-show"', 1)
            snippet = snippet.replace('class="ob-step"', 'class="ob-step force-show"', 1)
        cards.append((label, desc, snippet))

    board_html = '\n'.join(
        '<div class="pf-col"><div class="pf-label">' + label + '</div>'
        '<div class="pf-phone"><div class="pf-statusbar"><span>9:41</span>'
        '<span>📶 📡 🔋</span></div>'
        '<div class="pf-content">' + snippet + '</div></div></div>'
        for label, desc, snippet in cards
    )

    out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{TITLE}</title>
<style>
{base_css}
{FLAT_CSS}
</style>
</head>
<body>
<div class="copy-bar">
  <div>
    <div class="t">📋 {TITLE}</div>
    <div class="i">共 {len(cards)} 个状态 · 横向平铺 · 无交互 · 一键复制源码粘墨刀</div>
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
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'[ok] 生成 {out_path} · {len(cards)} 个状态 · {len(out)} 字符')


if __name__ == '__main__':
    main()
