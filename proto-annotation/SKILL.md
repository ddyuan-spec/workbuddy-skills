---
name: proto-annotation
version: 2.3.0
description: 给单文件 HTML 原型一键注入「批注层 Annotation Overlay」引擎（本地优先，file:// 直接可批注/同步）。角标独立浮层、动态跟随顶层弹窗、只显顶层弹窗内字段防穿透、列表可逐条删除/重定位/清理失联。可复用于 C 端 / 后台 / 任何单文件 HTML 原型。
type: user
---

# proto-annotation · 原型批注层（v4.3 · 本地优先 · 顶层弹窗隔离）

给任意单文件 HTML 原型注入一套批注引擎：黄底角标（独立浮层）挂在元素角上、点元素写批注、视图隔离、稳定编号、失联标记，批注存本地 localStorage；需要上线时可选两条路：①点「保存原型」导出带批注完整 HTML 覆盖回本地、交 WorkBuddy 推 GitHub；②双击 `run_anno_server.bat` 启动本地推送服务后，点「保存并推送」直推 GitHub（均无需 JSON 中转）。

## 适用场景
- 做了一套 HTML 原型（C 端 / 后台 / 小程序 / 平铺稿均可），想让评审人在本地点元素直接标问题，而不是口头/截图描述。
- 需要把批注沉淀进原型文件（而非散落在某人的浏览器 localStorage），并同步到 GitHub Pages 让所有人可见。
- 原型里有**弹窗 / 浮层**：批注引擎会自动做「顶层弹窗隔离」——开着弹窗时只显示该弹窗内字段的角标，背景与下层被盖弹窗的角标自动隐藏防穿透。

## 设计要点（v4 相对 v3 的改动 + v4.3 实战沉淀）
1. **本地优先，去掉域名门禁。** v3 要求 `*.github.io` 或 `?anno=1` 才能批注，本地 `file://` 按钮置灰。v4 直接放开：本地双击打开 HTML 即可批注/导出，无需先推 GitHub。（理由：用户本地改原型 + 批注，再一起推 GitHub 更顺；`file://` 下 localStorage 可用、稳定。）`canAnnotate=true` 硬编码在引擎头部，无门禁。
2. **角标独立浮层 `#__anno_layer`（pointer-events:none，角标本身 pointer-events:auto）。** v3 把角标 `appendChild` 进业务元素，宿主是 `<select>/<input>` 时角标 0 尺寸不可见、弹窗一开角标穿透到弹窗上。v4 角标统一挂固定浮层，按元素 rect 实时算坐标（滚动/resize/视图切换重算），**一次性消灭宿主 0 尺寸、气泡飘左上角**这一整类问题。
3. **顶层弹窗隔离（v4.3 核心，本次水卡批注实战沉淀）。** 角标浮层 z-index **动态跟随顶层弹窗**：无弹窗时回落 4000（高于常见遮罩 3950）；有弹窗开着时运行时设为「顶层弹窗 zIndex + 1」，始终压在最高弹窗之上又不盖死它。分类逻辑 `classify()`：用 `topOpenModal()` 取「开着且堆叠最高（zIndex 大者优先）的最外层弹窗根容器」，只显示该顶层弹窗内的字段角标；背景与下层被盖弹窗的字段一律 `hidden-modal` 隐藏防穿透。
   - **默认全量（关弹窗时）**：关着的弹窗内字段**不隐藏、落 pending 灰标**堆在右上角，打开弹窗即看全量（本次确认方案：默认不自动开弹窗，关着的弹窗字段先 pending，点了「定位」才展开对应弹窗并聚焦）。这解决了旧版"默认开弹窗遮背景"被评审否掉的体验问题。
   - `modalOf()` 与 `topOpenModal()` 必须**归并到最外层弹窗根容器**（穿透内容框 `.wct-modal/.cf-modal` 到遮罩层 `.wct-mask/.cf-mask`），否则 `m===top` 对象不等、误判 `hidden-modal`。
   - **runtime 弹窗显隐必须重分类**：`MutationObserver` 监听 `style/class` 变化触发 `renderThrottled()`（而非只重算坐标），否则运行时点击打开/关闭弹窗后隔离逻辑不刷新（这是真实原型里最容易踩的坑，v4.3 修掉）。
4. **通用激活钩子 `runActivate` / `autoActivate`（去硬编码）。** seed 条目可带 `activates:'函数名或JS片段'`，引擎 init 时 `autoActivate()` 跑各批注的 `activates` 让「条件字段」（需先触发某交互才出现）在 init 时就渲染出来以便定位；默认不打开弹窗。引擎不耦合任何具体业务（如 watercard），换成「选水卡才显示水卡设置」这类交互，只需在 seed 写 `activates:'syncWaterCards'`，原型实现该函数即可。
5. **localStorage 缓存比对（防旧缓存覆盖修复后 seed）。** 仅当缓存数组与文件 seed 的 **`id+sel+text` 完全一致**（合法编辑）时才用缓存；否则用文件 seed 并重写缓存。`text` 必须参与比对——seed 文案更新后，同 id+sel 的旧缓存不应继续生效（否则"打开即失联 / 旧文案不刷新"）。
6. **列表可操作。** 每条批注右侧常驻 `定位`/`删除`；失联的那条额外给 `重定位`（点一下进入拾取模式 → 点正确位置 → 只换锚点，编号/文字不变）；面板顶部 `清理失联(N)` 一键批量删。
7. **`locate` 多命中优先取可见者**，避免命中隐藏重复节点被误判失联。

## 强制门禁（铁律）
1. **禁止静默删除/移动用户批注。** 改原型动了元素结构、导致既有批注锚点失联时，必须先用批注列表的「失联」标记或导出 JSON 的 `valid` 字段列出受影响批注，逐条向用户确认「删除 / 保留 / 保留到哪个字段」后，才允许改。绝不允许静默清掉用户批注。v4 提供的「重定位」就是为此：失联批注不删、只换锚点。
2. **引擎是单一源，禁止直接改生产 HTML 里的引擎。** 改 `assets/engine.js` / `assets/engine.css` 后对所有目标跑 `inject_anno.py --force` 收口；否则会与单一源漂移。
3. **改完引擎必须跑 `verify_real.py` 四态真实回归（见文末），全 PASS 才算收口。** 校验用「全新 profile + `--dump-dom`」读真实失联态，**杜绝预激活骗过校验**（旧 `verify_v4.py` 用预激活，已不作为唯一判据）。
4. **数值/枚举/格式类批注，口径不明一律反问，禁止臆造。** 写「输入限制」「枚举值」「单位」「格式规则」这类批注时，若产品未给定明确口径（如数值范围、精度是小数还是整数、最小值、单位换算），必须**先反问用户**确认，绝不自己填 0.1~9999、1~999 这类"合理猜测值"。反例：取水上限类本应是整数且最小 1，臆造 0.1~9999 小数范围被用户打回，并连带要清旧缓存。**已给定确认过的口径才能落文案**（如有效期 1~3650 天、取水上限正整数最小 1）。

## 工作流（完整闭环 · 本地优先 · 无 JSON 中转）
```
① 建原型(无批注) → ② inject 注入引擎（或已在文件里）
③ 本地双击打开 file:// → 点「批注」写问题（存 localStorage，自动保存）
④ 需要上线时：点「保存原型」→ 下载带批注的完整 HTML（__anno_seed 已内嵌）→ 覆盖回本地原型文件
⑤ 把该 HTML 交给 WorkBuddy → 直接 gh_push 推 GitHub Pages → 全员可见
```
> 「保存原型」导出的是**整份自包含 HTML**，批注已写回 `<script id="__anno_seed">`，不依赖任何 JSON 文件；浏览器无法回写源文件，故由下载+覆盖+AI 推送完成落盘。

### 步骤② 注入引擎（幂等）
```bash
python scripts/inject_anno.py --html path/to/proto.html          # 首次注入
python scripts/inject_anno.py --html path/to/proto.html --force  # 升级/收口到最新（先剥离旧引擎再注入，并保留已有 __anno_seed）
python scripts/inject_anno.py --dir path/to/protos              # 整目录批量
```
注入内容：`<style id="__anno_css">` + `<script id="__anno_seed" type="application/json">` + `<script id="__anno_engine">`，内联在**最后一个** `</body>` 前（见「注意」），单文件自包含。

### 步骤③ 本地批注（浏览器内）
工具栏（右下角，z-index 最高，弹窗开启时仍可用）：**批注 / 隐藏 / 列表 / 保存原型 / 保存并推送 / 清空**
- 点「批注」进入批注模式 → 点任意元素 → 弹框写文字 → 保存即生成角标（黄底数字；同锚点多条合并显示为橙色计数）。
- **角标常显，挂在独立浮层，按元素实时定位**：小元素（单选项/按钮/输入框）角标贴在它身上；**弹窗开启时只显该弹窗内字段角标，背景/下层弹窗角标自动隐藏（防穿透）；元素完全滚出视口时角标隐藏、滚回再现**（方案A，修掉旧版滚出后被 clamp 吸附钉在屏幕边缘的问题）。
- 切到别的视图（`.view/.page`）批注自动隔离（按 `currentView()` 判定 `.view.active/.page.active`）。
- 「列表」面板：每条批注显示 编号 / 视图归属 / 挂载位置文字 / 时间；失联的标红并给 `重定位` 按钮；顶部有「清理失联(N)」。点列表「定位」会自动展开对应弹窗（若该字段在弹窗内）并高亮字段。
- 「隐藏」临时收起所有角标（截图/演示干净版用），「显示」恢复。
- 「保存原型」：把当前批注写回 `__anno_seed` 并导出**完整 HTML**（文件名=原型文件名），用户覆盖回本地原型即可；之后把该 HTML 交给 WorkBuddy 直接推送。
- 「保存并推送」：需先启动本地 `anno_push_server`（见步骤⑥）；点一下把带批注 HTML 直接推 GitHub Pages（本地原型同步更新），无需经 WorkBuddy。

### 步骤④⑤ 保存并推 GitHub（无 JSON）
评审在本地批注完（存 localStorage），点「保存原型」下载带批注的整份 HTML。用户覆盖回本地原型文件，然后把该 HTML 交给 WorkBuddy：
```bash
# 直接推这份 HTML（批注已内嵌 __anno_seed，无需解析 JSON）
python ../../delivery-suite/scripts/gh_push.py --repo OWNER/REPO --root <本地仓库根> \
    --put <file>.html::<file>.html::同步批注 --wait-pages --live-grep "<file>.html::__anno_seed"
```
推送后线上所有人打开链接即可见角标，刷新不丢。`anno_push.py`（旧 JSON 中转器）已弃用。

### 步骤⑥ 一键直推（本地服务中转，推荐）
不想每次把 HTML 交 WorkBuddy？在**本机**双击 `run_anno_server.bat`（或 `python anno_push_server.py`）启动一个常驻后台服务（监听 `127.0.0.1:8765`，只本机可达），然后原型页点「保存并推送」即可把带批注 HTML 直推 GitHub Pages——服务用**已登录的 `gh` CLI** 推送，token 不进浏览器。
- 服务脚本：`anno_push_server.py`（项目根目录）；启动器：`run_anno_server.bat`。两者随原型文件一起放在仓库根。
- 推送时：原型页把当前 HTML POST 给服务 → 服务写回本地原型 + 调 `gh_push.py` 推 GitHub → 返回成功/失败 toast。
- 失败不影响本地：本地原型已更新，可重试。
- 仅本机回环监听，不外网暴露；Ctrl+C 退出服务。
- 适用前提：本机 `gh` 已 `gh auth login`（用户日常已登录），且网络可达 GitHub（梯子开着）。

## 锚点规则（`anchorOf`）
角标挂哪只决定「角标贴在哪个元素的角」，浮层只按该元素 rect 算坐标。**不再受宿主能否容纳子节点影响**（v4 已解耦）：
1. `[data-anno]` 显式业务锚点（最优先；给关键区域埋这个 key，改版永不漂）。
2. **小元素挂自己**：目标是原子元素（`label/button/a/input/select/textarea/img/svg/i/em/strong/code/span/td/th/dt/dd/li/p/h1-6`）且高度 ≤ 44px → 直接挂它自己；点 `input[type=radio|checkbox]` 小圆点时先提级到包它的 `label`。
3. **最近小容器**：`.fr,.ctl,.form-item,.row,.item,.cell,.field,.col,tr,li,td,th,.box,.card,section,article,form` 中高度 ≤ 220px 的第一个。
4. 兜底：目标元素自己。

### 角标位置模式（浮层内由 `positionFlags` 计算）
- 锚点尺寸正常 → `corner`：挂右上角（`right-9 / top-9`）。
- 锚点极小（高或宽 < 22px）→ `side`：挂右侧外廓（垂直居中），免得角标盖死小元素。

## 弹窗感知与顶层隔离（v4.3 算法细节，改引擎前必读）
原型里弹窗容器类名很多样（`.wct-mask/.wct-modal/.cf-mask/.cf-modal/.mask/.modal/.dialog/.overlay/.popup` 等），`MODAL_SEL` 一次性枚举这些。核心三函数：

- **`modalOf(el)`**：从元素向上 `closest(MODAL_SEL)`，再**归并到最外层根容器**（若父链上还有弹窗容器则继续穿透），返回最外层根。这样内容框 `.wct-modal` 和遮罩层 `.wct-mask` 归一到同一根，分类比较才一致。
- **`topOpenModal()`**：`querySelectorAll(MODAL_SEL)` → 同样归并到最外层根（去重）→ 取「`isModalOpen` 为真 且 `getComputedStyle.zIndex` 最大」的那一个；无弹窗开着返回 `null`。`isModalOpen` = display≠none 且 rect 尺寸 >0。
- **`classify(a)`**：`el=locate(...)`；`m=modalOf(el)`；`top=topOpenModal()`。
  - `top` 存在：仅 `m===top` 返回 `ok`/`pending`（顶层弹窗内）；其他一律 `hidden-modal`（背景与下层被盖防穿透）。
  - `top` 为 `null`（无弹窗开）：`el` 可见 → `ok`；否则 `pending`（**关着的弹窗内字段落 pending，默认全量**）。
  - `el` 定位失败 → `pending`（有 fallback）或 `lost`（彻底失联，红标）。
- **`positionFlags()` 动态 z-index**：`var top=topOpenModal(); var topZ=4000; if(top){ var z=parseInt(getComputedStyle(top).zIndex||'0',10)||0; topZ=(z>4000?z:4000)+1; } layer.style.zIndex=topZ;`——浮层始终压在最高弹窗之上 1 档，不盖死它。
- **runtime 重分类**：`vmodal` MutationObserver 监听 `style/class` 变化 → `renderThrottled()`（含 `positionFlags`），弹窗运行时开/关都会重新算 `top` 与分类。

> ⚠️ 注入顺序陷阱：`buildAnnotatedHtml`/调试时若把新弹窗插在引擎**之后**（引擎 init 时它尚不存在），init 那次 `render` 看不到它；正确做法是先改好 DOM（打开弹窗/插入覆盖弹窗）再注入引擎，或在 seed 用 `activates` 让引擎自己触发。`verify_real.py` 已按此构造四态。

## 文件结构
```
proto-annotation/
├─ SKILL.md
├─ scripts/
│  ├─ inject_anno.py   # 注入/升级引擎（幂等，--force 保留 seed）
│  ├─ verify_real.py   # 【权威】改完引擎必跑的 headless 四态真实回归（默认全量/开弹窗隔离/多弹窗顶层覆盖/下层被盖）
│  ├─ sample_proto.html# 最小可注入样例（12 背景字段 + 7 弹窗字段 + 顶层覆盖弹窗构造），供 verify_real.py 与手测
│  ├─ verify_v4.py     # 旧版回归（预激活，仅锚点降级+合并删除，保留备用，不作为唯一判据）
│  └─ verify_anno.py   # 旧版回归（仅锚点降级+合并删除，保留备用）
└─ assets/
   ├─ engine.js        # __anno_engine 单一源（本地优先，无门禁，含顶层弹窗隔离）
   └─ engine.css       # 工具栏/浮层/角标/气泡样式（layer z-index 回落 4000，运行时动态跟随）
```
引擎以 `assets/` 为单一源；升级时改 `assets/` 后对所有目标跑 `--force`。

## 注意
- 批注锚点是 CSS 选择器，原型大改版后旧批注可能失联；列表里标红 + 给「重定位」，按门禁①逐条确认处理，**不静默删**。
- `inject_anno.py` 必须注入到**最后一个** `</body>` 前：原型里常含「复制源码」功能，返回值字符串有字面量 `</body>\n</html>`（如 C 端 `__protoBuildStandalone`）；取第一个 `</body>` 会塞进 JS 字符串 → 真实 DOM 无批注层。任何往原型插块的脚本同理。
- `--force` 会保留已有 `__anno_seed`（线上批注数据），不会误清空。

## 已知失效模式（v3 的血泪，v4 / v4.3 已修）
- **R1 宿主不能容纳子节点 → 角标 0 尺寸不可见**（`<select>/<input>/<img>`/`display:contents` 被当 atom 后 `appendChild` 进去）。**v4 浮层解耦，已根治。**
- **R2 选择器多命中取了隐藏的那个 → 误判失联**。**v4 `locate` 多命中优先取可见者，已根治。**
- **R3 角标 rect 归零后气泡飘左上角**。**v4 气泡定位用目标元素 rect，已根治。**
- **弹窗穿透（旧 v4 也有）**：角标浮层若固定 z-index 低于弹窗遮罩，弹窗一开角标被遮；若固定高于遮罩，又会盖死弹窗。**v4.3 改为动态跟随顶层弹窗（`topOpenModal` 取最高 zIndex +1），只显顶层弹窗内字段、其余 `hidden-modal` 防穿透，已根治。**
- **旧缓存覆盖修复后 seed（本次实战）**：localStorage 旧缓存导致"打开即失联 / 旧文案不刷新"。**v4.3 改为 `id+sel+text` 全比对，不一致即用文件 seed 重写缓存，已根治。**
- **runtime 弹窗开/关不刷新隔离（本次实战）**：MutationObserver 旧版只重算坐标不重分类，运行时点开/关弹窗后隔离失效。**v4.3 改为触发 `renderThrottled` 重新分类，已根治。**

## 回归验证（改完 engine 必跑 · 权威）
```bash
node --check assets/engine.js
python scripts/verify_real.py                 # 校验内置 sample_proto.html 四态
python scripts/verify_real.py --html 你的原型.html   # 校验任意已含 __anno_seed 的原型
```
`verify_real.py` 用「全新 profile + `--dump-dom`」读真实失联态，校验四态（全部基于真实渲染，非预激活）：
1. **态A 默认（弹窗关）**：角标总数 == seed 数（全量，19），无失联；关着的弹窗内字段落 `pending` 堆右上角。
2. **态B 开弹窗**：只显示弹窗内字段角标（`ok` 仅弹窗内），背景字段隐藏、无 `pending`。
3. **态C 多弹窗（顶层覆盖 z=9999 且无字段）**：上层覆盖 → **0 角标**（下层弹窗不穿透到顶层）。
4. **态C2 多弹窗（下层被盖 z=1000）**：下层 → 仍只显示顶层（`wctMask`）内字段。

四态全 PASS 才算收口。C 端 / 异构原型若无匹配测试元素，会软跳过角标精度校验（引擎代码与后台完全一致，已在样例验证）。
