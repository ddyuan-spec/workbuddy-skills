# PRD 截图对齐（prd-screenshot-sync）

## 何时用
PRD / 需求文档里用 `<img>` 内嵌了**原型截图**（平台端/App/小程序等的界面图），而原型 HTML 经历过改版（配色修正、UI 重构、删除序号、字段增删等）。每次原型改动后，**PRD 里的截图极易悄悄过期**——用户看到的是老图，但 PRD 文字已写新逻辑，造成"图文不一致"。

触发词：截图过期了 / 原型改了截图没换 / 重截 PRD 图 / 确认 PRD 图片是最新的 / 截图还是老的。

## 强约束（踩坑固化）
1. **禁止用 `<iframe>` 加载原型再截图**。file:// 下的 iframe 跨域会让 `contentDocument` 取不到、注入的触发脚本不执行，结果是多张"不同视图"截出**完全相同的图**（字节一致）。本 skill 改为：把触发脚本注入【原型 HTML 的临时副本】再直接截图，彻底避开跨域。
2. **必须加 `--virtual-time-budget=3000`**。Edge `--screenshot` 在 `load` 事件即截，若触发弹窗/切视图写在 `setTimeout` 里会还没跑就被截掉，所有图回到初始态。该参数让定时器先跑完再截。
3. **雷同自检**：截完用 PIL 看 `distinct_colors` 和 `top_color` 占比。若两张"不同视图"字节/颜色分布完全一致 → 触发器没生效，立刻告警，不要假装成功。
4. **MD5/size diff**：只替换真正变化的图，并打印 `[NEW/CHANGED/unchanged]`，方便确认"到底哪几张过期了"。
5. **推 GitHub 用 Python 生成 body.json + `gh api --input`**，绝不用 `printf "$(cat b64)"` 传超长 base64（Windows Git Bash 会静默截断）。推送后 `curl raw.githubusercontent.com` 回读验证 HTTP 200。
6. 截图换完后，**重生成 Word**（如有）用 `html-to-docx` skill，确保 Word 内嵌的也是新版图。

## 用法
```
python recap_shots.py --map PRD/screenshot-map.json [--push] [--dry]
```
- `--map`：JSON，描述每个截图对应的原型触发脚本与窗口尺寸（见 references/screenshot-map.example.json）。
- `--push`：重截后直接推 GitHub Pages（默认仓库 ddyuan-spec/taixiaohu，资源路径 hlz-prd-assets/）。
- `--dry`：只检查不替换。

## 工作流程
1. 先扫 PRD 里所有 `<img src="...本地png">`，与 map 文件核对，缺哪个视图补哪个。
2. 对每个图：注入触发脚本到原型临时副本 → Edge headless 截图（带 virtual-time-budget）→ 与旧图 diff。
3. 雷同自检：发现不同视图字节一致 → 报错并停下，检查 trigger 函数名/参数是否与当前原型一致（原型重构后函数可能被改名/删除）。
4. 替换过期图，推 GitHub（如需要），重生成 Word（如需要）。
5. 回复用户：列出"哪几张图被更新 / 哪几张本来就是最新的"，并给 GitHub 链接。

## 依赖
- Edge (headless) 路径自动探测：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` 或 `C:\Program Files\Microsoft\Edge\...`
- Python `Pillow`（自检用，缺了会跳过自检但流程照跑）
- `gh` CLI 已登录（推送用）
