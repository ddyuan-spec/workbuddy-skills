# -*- coding: utf-8 -*-
"""
html-proto-screenshot · 通用截图脚本
====================================
把「单页多 screen」HTML 原型按指定屏幕/状态批量渲染为 PNG。

固化经验（详见 SKILL.md）：
  1. 用 playwright 自带 chromium，绝不用 MS Edge --screenshot（时机不可靠）。
  2. 改造单页原型的两大陷阱：
     A. body 正则必须 <body>(.*?)<script> 截到 <script> 之前，
        否则原 <script> 的 const 与 pre_init 重复声明 → SyntaxError → 全截成第一屏。
     B. pre_init 在 function init() 处截断，绝不调用 init()，
        否则 init() 把页面切回默认屏覆盖 customInit。

用法：改下方 SRC/OUT/TMP/CHROME + JOBS，跑：
  python capture_proto.py
"""
import os, re, subprocess, hashlib, collections, shutil

# ===== 1. 配置（按需修改） =====
SRC    = r'C:/Users/13364/WorkBuddy/任务目标流程化/泰小虎-睡眠任务闭环C端原型-v7.html'   # 源单页 HTML
OUT    = r'C:/Users/13364/WorkBuddy/任务目标流程化/prd-assets'                            # 输出 PNG 目录
TMP    = r'C:/Users/13364/WorkBuddy/任务目标流程化/_shot_tmp'                            # 临时 HTML 目录
BACK   = r'C:/Users/13364/WorkBuddy/任务目标流程化/_shot_tmp/old'                        # 旧图备份
CHROME = r'C:/Users/13364/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe'  # 注意：chromium-1234 版本号可能随 playwright 更新变化，用前 ls $LOCALAPPDATA/ms-playwright/ 确认实际路径
WIN    = '440,880'   # 视口尺寸，按原型调整

# ===== 2. 拆源 HTML =====
src     = open(SRC, encoding='utf-8').read()
style   = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
body    = re.search(r'<body>(.*?)<script>', src, re.S).group(1)          # 陷阱A：body 截到 <script> 前
script_full = re.search(r'<script>(.*?)</script>', src, re.S).group(1)
pre_init = script_full.split('function init()', 1)[0]                    # 陷阱B：截断在 init() 前
ut = re.search(r'function updateTime\(\)\s*\{.*?\n\}', script_full, re.S).group(0)  # 抽出独立函数

def build(init_body):
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>shot</title><style>{style}</style></head><body>{body}<script>{pre_init}{ut}'
        f'function customInit(){{ {init_body} }}\n'
        'customInit();'
        '</script></body></html>'
    )

# ===== 3. 截图任务列表（示例为 v7 原型，按需改） =====
# 每项 = (输出文件名, customInit 语句：先 updateTime() 再 go('page-xxx')+渲染)
JOBS = [
  ('c-notification',  "updateTime(); go('page-notification');"),
  ('c-home',          "updateTime(); state.dailyReportShown=true; go('page-home'); renderAll();"),
  ('c-tasks-list',    "updateTime(); state.dailyReportShown=true; state.myTasks=['t1','t3','t7']; state.completedToday=[]; state.huLi=0; go('page-tasks'); renderAll();"),
  ('c-completion',    "updateTime(); state.dailyReportShown=true; state.myTasks=['t1','t3']; state.completedToday=['t1']; state.huLi=5; go('page-tasks'); renderAll(); showOverlay('overlay-completion');"),
  ('c-huli',          "updateTime(); state.dailyReportShown=true; state.huLi=128; state.myTasks=['t7']; state.completedToday=[]; go('page-huli'); renderHuli();"),
  # …… 其余屏幕照此格式追加
]

# ===== 4. 执行 =====
os.makedirs(BACK, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
results = []
for name, ibody in JOBS:
    html = build(ibody)
    tmp_html = os.path.join(TMP, f'{name}.html')
    open(tmp_html, 'w', encoding='utf-8').write(html)
    out_png = os.path.join(OUT, f'{name}.png')
    if os.path.exists(out_png):
        try: shutil.copy2(out_png, os.path.join(BACK, f'{name}.png'))
        except Exception: pass
    src_url = 'file:///' + tmp_html.replace('\\', '/')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
           '--force-device-scale-factor=2', '--virtual-time-budget=4000',
           f'--window-size={WIN}', f'--screenshot={out_png}', src_url]
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    ok  = os.path.exists(out_png)
    sz  = os.path.getsize(out_png) if ok else 0
    md5 = hashlib.md5(open(out_png,'rb').read()).hexdigest() if ok else ''
    results.append((name, ok, sz, md5[:8]))
    print(f'{name:20s} OK={ok} {sz:>7d}B md5={md5[:8]}')

# ===== 5. 校验：md5 去重计数（全部相同=失败） =====
sizes = collections.Counter([r[3] for r in results])
print('\nUnique md5s:', len(sizes), '— 若 ==1 则 customInit 未生效，全部截成同一屏')
for md, c in sizes.items(): print(' ', md, 'x', c)
