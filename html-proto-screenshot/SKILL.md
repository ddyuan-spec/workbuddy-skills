---
name: html-proto-screenshot
description: 当用户需要把「单页多屏幕（single-page multi-screen）HTML 原型」按指定屏幕/状态批量渲染为 PNG 截图时使用——典型场景：把 App/H5/小程序单文件 demo 的某一屏截成图放进 PRD/docx/评审材料、原型迭代后重截全部配图刷新文档、或遇到「Edge 截图全一样/只截到第一屏」等渲染时机问题。固化使用 playwright 自带 chromium（非 MS Edge）的可靠渲染参数，以及改造单页多 screen 原型的两大致命陷阱。
---

# Html Proto Screenshot

## Overview

把已存在的「单页多屏幕」前端原型（单个 HTML 文件内含多屏，靠 JS 切换 visible 页面）按指定屏幕/状态批量渲染为 PNG 截图，用于 PRD 文档配图、评审交付或迭代刷新。本 skill 固化了可靠的渲染命令与改造原型的两条致命陷阱，避免踩「截图全部变成同一张第一屏」的坑。

## When To Use

- 需要把 HTML 原型（App / H5 / 小程序单文件 demo）的某一屏截成图，放进 PRD / docx / 评审材料。
- 原型迭代后需要「重截」全部配图刷新文档。
- 遇到 MS Edge `msedge --screenshot` 截出来全一样、或只截到第一屏等渲染时机问题。

## 渲染引擎选择（关键）

- **禁止**用 MS Edge 的 `--screenshot` 参数做多屏截图：新版 Edge headless 截图时机不可靠，13 张会全部截成同一张第一屏（on-load 截屏，不等 JS 跑完）。
- **必须**用 playwright 自带 chromium（本机路径 `C:\Users\13364\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe`），配合 `--virtual-time-budget=4000` 等待 JS 渲染完成后再截。

## 命令模板

```
CHROME="C:/Users/13364/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 --virtual-time-budget=4000 \
  --window-size=440,880 --screenshot=OUT.png "file:///.../tmp.html"
```

要点：`--virtual-time-budget=4000` 是等待 JS 渲染的关键；`--force-device-scale-factor=2` 提清晰度；`--window-size` 按原型视口（手机原型常见 440x880）。

## 单页多 screen 原型改造（两条致命陷阱）

原型通常是 `<body>` 内含多个 `.page`（默认 display:none，靠 `go('page-xxx')` + `init()` 切换），不能直接截。需为每张图构造一个「临时 HTML」，只激活目标屏。

构造临时 HTML 的正确做法：

1. 从源 HTML 拆出三段：`style`、`<body>(.*?)<script>` 之前的 body（**必须用 `<script>` 之前的 body**）、`script` 内的「前置定义」（数据 / state / 函数，**在第一个 `function init()` 之前截断**）。
2. 单独抽出需复用的独立函数（如 `updateTime()`），用正则 `function updateTime\(\)\s*\{.*?\n\}` 抽取。
3. 自定义切换逻辑写进 `customInit()`，在脚本末尾调用 `customInit();`：内部先 `updateTime();` 再 `go('page-xxx');`（必要时补 `renderAll()/renderXxx()`）。
4. 临时 HTML = `<style>{style}</style><body>{body}<script>{pre_init}{ut}function customInit(){...}customInit();</script>`。

**陷阱 A — 绝不把原 `<script>` 完整包进临时 HTML**：原 script 含 `const ALL_TASKS` 等顶层声明；若连同原 script 一起引入，会与 pre_init 中重复声明 → `SyntaxError: Identifier 'ALL_TASKS' has already been declared` → 整个脚本崩溃 → 页面停在初始（第一屏）→ 所有截图全一样。**`body` 正则必须 `<body>(.*?)<script>` 截到 `<script>` 前，`pre_init` 只取 `function init()` 之前的片段。**

**陷阱 B — 绝不引入 `init_def` / 调用 `init()`**：原型的 `init()` 会把页面切回默认屏（通常是 `page-notification`）。若临时 HTML 末尾同时有 `customInit()` 和 `init()`，后者覆盖前者，截图永远是第一屏。解决方案：`pre_init` 在 `function init()` 处截断（不包含 init 定义与调用），只保留 `customInit()`。

**陷阱 B 的例外 — 后台 SPA 原型可走「单一入口替换」简化分支**：若原型（典型：绿韵家 `*-admin-*proto.html`）满足 ① script 里**没有** `function init()` ② 末尾只有一句入口调用如 `go('member');` ③ 靠 `go(key)` + `openXxxEdit()` 切屏 —— 则**不需要** pre_init 截断 / customInit 那套复杂构造，直接：
```python
out = src_html.replace("go('member');", "go('cost'); openCostEdit();")
```
写临时 HTML 后截图即可。表单/抽屉类子页用 `go('父view'); openXxx();` 组合打开（如 `go('promptConfig'); openPromptGroupEdit();`）。

**后台 SPA 截图参数**：`--window-size=1440,900` + `--force-device-scale-factor=2`；后台是 top-bar + sidebar 满屏固定布局，**不会踩陷阱 D 的空白问题**（内容天然到底）。截完建议用 PIL 把 2880 宽 resize 到 1440 降体积（默认截图 ~300–410 KB → 降到 ~110–350 KB）。

**切屏是否生效的验证（比 md5 去重更强）**：md5 不同只能证明「不是同一张」，不能证明「截对了目标屏」。注入 JS 把激活 view 写进 title 再 `--dump-dom` 读回：
```js
;(function(){var vs=document.querySelectorAll('.view'),act=[];
for(var i=0;i<vs.length;i++){if(getComputedStyle(vs[i]).display!=='none')act.push(vs[i].id);}
document.title='ACTIVE='+act.join(',');})();
```
期望输出 `ACTIVE=viewCostEdit` 这类**单一且正确**的 id；若出现多个 id 或 id 不符，说明切屏失败。

## 校验（必做）

截完必须校验：对每张 PNG 算 md5，**若全部相同 = 仍失败**（说明 customInit 没生效、页面没切换）。正常应每张都不同。脚本末尾已内置 md5 去重计数打印。

## 陷阱 C — 原型顶部 sticky 工具栏（copy-bar / 复制源码条）污染 PRD 截图

项目里很多原型为了交付演示，顶端会加一条 `position:sticky;top:0;z-index:9999` 的「复制源码」工具栏（`<div class="copy-bar">`，含「复制当前页 / 复制全部源码」按钮），这属于**原型交付辅助**，**不是产品功能**。如果 capture 时不隐藏，所有截图都会被这条 ~50px 高的黑/深色 bar 压住顶部并把内容下推——结果就是 PRD 截图位置整体下移、和原型脱节。

**症状**：截图顶部出现 `📋 <文件名>` + 「复制当前页/复制全部源码」按钮；产品内容从 bar 下方才开始。

**修复（capture 时注入 CSS 隐藏）**：在 build 出的临时 HTML 的 `<style>` 末尾追加：

```css
.copy-bar,.copy-toast{display:none!important}
```

（具体 class 名按实际 prototype 的工具栏 class 调整；常见还有 `.copy-bar__*`。）

**适配绿韵家 `newuser-gift-c-app.html` 用的类名**：
- `.copy-bar`（外层 sticky 顶栏）
- `.copy-toast`（底部浮动 toast，截图里偶尔也会显示）
- 两者都隐藏即可，**不要尝试保留**（PRD 不该出现交付辅助 UI）

⚠️ 真实案例：2026-09-03 绿韵家新人激活码礼包 PRD 11 张 C 端截图全部带顶部 copy-bar，re-capture 时注入 `display:none!important` 后 11/11 干净上线。

## 陷阱 D — 截图四周大段空白（viewport 高于内容）

**症状**：PRD 里某张截图上半段有内容、下半段（或四周）一大片灰底/白底空白，整体像"把整张长画布拍了下来"。用户会直接说"这图不对，大量空白"。

**根因**：chromium `--screenshot` 是按 **`--window-size=W,H` 指定的整个视口**截的，不是"只截有内容的部分"。如果给的 `WIN='440,1900'` 之类远大于单屏内容高度（多数手机原型单屏只有几百 px 高），就会拍出"小手机浮在大画布中央 + 大片空白"。

**修复（二选一，推荐方案 1）**：

**方案 1 · 按内容真实高度截（最干净，无需 Pillow）**：
1. **第 1 pass**：用 `--dump-dom` 或注入 `--run-all-compositor-stages-before-draw --virtual-time-budget=2000` 渲染后，在 `customInit` 里 `go(target)` 激活目标屏；
2. 用 JS 在页面里读出**内容真实高度**：`document.querySelector('.phone, .page.active, #app').scrollHeight`（按原型实际根容器类名），或 `document.body.scrollHeight`；
3. **第 2 pass**：用这个真实高度作为 `--window-size=W,{真实高度}`，再 `--screenshot`。此时视口 == 内容，零空白；
4. 若原型有 `margin:20px auto` 之类外边距导致左右留白，临时 HTML 注入 `style="margin:0!important"` 再截，或截图后裁掉。

**方案 2 · 截后 PIL 裁切（兜底）**：
- 截图后 `from PIL import Image`，采样四角 20×20 像素作为背景色 → 找"与背景像素差 > TOL(6)"的 bbox → `crop()` 去掉四周留 8px padding。鲁棒但多一层依赖，且对透明/渐变背景要调 TOL。

**验收钩子**：打印每张图的 `pngH` 与 `2×内容高度` 比对——若 `pngH == 2×内容高度`（device-scale-factor=2）且远小于 `2×1900`，说明已无空白。若某张 `pngH` 仍接近 viewport 高度，就是又踩坑了。

⚠️ 真实案例：2026-09-07 绿韵家新人激活码 PRD 13 张 C 端截图全部带上下大段空白（首版 `WIN='440,1900'`），改用"2-pass 按 `.phone` 真实高度截"后 13/13 内容裁切干净重新上线。

## 脚本

`scripts/capture_proto.py` 是通用模板：读取源单页 HTML，按 `JOBS` 列表（每项 = 输出文件名 + customInit 语句）循环构造临时 HTML、调 chromium 截图、打印 md5 去重校验。复制后改 `SRC / OUT / TMP / CHROME` 与 `JOBS` 即可复用（v7 原型已作为示例 JOBS 内置）。

## 关联

本项目（任务目标流程化）的同源 PRD 工作流见 `build_prd.py → check_prd 验证 → _push_prd.py 推送`，截图刷新后需 rebuild + 推送 GitHub Pages 才能刷新线上。离线 docx 用 HTML→DOCX 按线上源重生以保持一致。
