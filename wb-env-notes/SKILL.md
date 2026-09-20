---
name: wb-env-notes
description: 跨项目 WorkBuddy 环境与工具坑速查（只读参考）。覆盖 managed Python venv 布局与缺失项、SVG 栅格化回退方案、阿里云 OSS 内网可达性、WorkBuddy Bash 空输出故障自查、Git Bash 内联 python -c 转义陷阱、HTML→DOCX 转换 venv 入口。当任务涉及本地渲染/截图/远程图下载/环境异常排查时查阅，避免重复踩坑。
---

# 跨项目环境与工具坑速查（wb-env-notes）

> 本 skill 是纯参考备忘，不定义门禁。环境事实类内容从 `~/.workbuddy/MEMORY.md` 迁出集中于此，避免记忆文件膨胀。

## 1. managed Python venv 布局（Windows）
- **docx 转换 venv**：`C:/Users/13364/.workbuddy/binaries/python/envs/docx/Scripts/python.exe`
  - Windows 布局 `Scripts/python.exe`，**非** `bin/python`。
  - 预装：python-docx / beautifulsoup4 / lxml / svglib / reportlab。
  - **缺失**：openpyxl、Pillow。要写 .xlsx 或在 xlsx 嵌图，须用 managed Python 3.13：`C:/Users/13364/.workbuddy/binaries/python/versions/3.13.12/python.exe`（openpyxl 预装，Pillow 需 `pip install Pillow`，网络可达）。
  - ⚠️ 该 venv 是 Windows 版 python.exe，**不接受 `/c/...` 风格路径**；调用用 `C:/Users/...` 正斜杠或 `C:\...` 反斜杠，否则报 `C:\c\...` 找不到文件。
- 调用约定：一律用绝对路径；Node 依赖 `NODE_PATH=C:/Users/13364/.workbuddy/binaries/node/workspace/node_modules`。

## 1.5 HTML → PDF 打印（简历/文档交付，2026-09-08 实证）
- 本机**无 LibreOffice / Word**，docx→PDF 只能让用户手动；但 **HTML→PDF 可本机搞定**：用 Edge headless 打印。
  ```bash
  cd "<目标目录>" && "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
    --headless=new --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="C:/绝对路径/输出.pdf" "file:///C:/绝对路径/输入.html"
  ```
- 要点：
  - 输出/输入都用 `C:/...` 正斜杠绝对路径；**不要**用 `/tmp`（会被解析成 `C:\tmp`），不要依赖相对路径。
  - `--no-pdf-header-footer` 去掉页眉页脚（默认会带 URL + 页码，很丑）。
  - 页面尺寸由 CSS `@page { size: A4; margin: 12mm 13mm; }` 控制；块级元素加 `page-break-inside: avoid` 防断页。
  -  stderr 会刷 `fallback_task_provider` / `GetUpdates... Network error` 之类 ERROR，**属正常噪音**，只要出现 `xxxxx bytes written to file` 就是成功。
  - 用 `pypdf`（`envs/pdfread/site-packages`）验页数：
    `PYTHONPATH="C:/Users/13364/.workbuddy/binaries/python/envs/pdfread/site-packages" <python> -c "from pypdf import PdfReader; print(len(PdfReader(r'路径').pages))"`
  - ⚠️ 注意 word matrix：本机的 pdfread / whisper 等 env **只有 site-packages，没有 python.exe**，须借 `C:/Users/13364/AppData/Local/Programs/Python/Python312/python.exe` + PYTHONPATH 跑；只有 docx env 有完整解释器。
  - Windows 上 Chrome 未装，只有 Edge，写路径别用 `chrome.exe`。

## 2. SVG→图片栅格化（2026-08-11 踩坑）
- ⚠️ 当前 Windows 沙箱 **cairosvg 不可用**（`OSError: no library called "cairo-2"`，系统缺 libcairo-2.dll）。
- 回退（纯 Python，docx venv 已预装）：
  ```python
  from svglib.svglib import svg2rlg
  from reportlab.graphics import renderPM
  renderPM.drawToFile(drawing, 'out.png', fmt='PNG')
  ```
- 局限：svglib 对 CSS 动画 / 外部字体 / 滤镜支持有限；纯几何 + 文本 + 基本样式的脑图 / 流程图 OK。需把 SVG 嵌 Word（python-docx 不认 .svg）或 Excel 缩略图时，别再试 cairosvg。

## 3. 阿里云 OSS 内网可达性（2026-08-11 实证）
- 沙箱里 `*.oss-cn-zhangjiakou.aliyuncs.com` **直连可达**：
  ```python
  urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})  # 25s 超时拉 PNG/JPG
  ```
- 涉及 alidocs / 钉钉文档导出的远程图，下载本地后用 Read 工具多模态 OCR（Read 支持 PNG/JPG）。

## 4. WorkBuddy Bash/PowerShell 空输出故障自查
- 症状：工具返回空输出 + 退出码 1（连 `echo`/`date` 都失败）。
- 排查（用 Glob/Read/Grep，不依赖 shell）：
  ① 实测 Bash 与 PowerShell 是否双双失效；
  ② 查 PortableGit `C:\Users\13364\.workbuddy\vendor\PortableGit\bin\bash.exe` 与 `usr\bin\bash.exe`+`msys-*.dll` 完整性（WorkBuddy 用的不是系统 Git）；
  ③ 查 sandbox 日志 `C:\Users\13364\.workbuddy\logs\sandbox\YYYYMMDD\` 是否进程 spawn 后 exit 1 且零输出（典型=客户端 sandbox 执行器故障）；
  ④ 主日志 `C:\Users\13364\AppData\Local\WorkBuddy\logs\main.log`。
- 多数=客户端 sandbox 偶发抽风，**重启客户端多自愈**；PortableGit 真损坏才清 `~/.workbuddy\workspace` 缓存或重装。

## 5. Git Bash 内联 python -c 转义陷阱
- 内联 `python -c "..."` 长脚本（含引号/反斜杠/多行）常被 shell 转义搞乱，致语法错误或静默错。
- 一律写成 `.py` 文件再 `python xxx.py` 执行，不在 Bash 内联长 python。

## 6. HTML→DOCX 转换入口
- 忠实转换（保留标题层级/表格边框/图片嵌入/标签色块/列表/中文 UTF-8 不乱码）直接用 docx venv 跑脚本。
- 与钉钉/Word 交付链路的编排见 `prd-to-dingtalk` / `tencent-docx` skill。

## 7. ⚠️ Bash 工具输出把 UTF-8 显示成 GBK（中文「假乱码」）——禁止据此判定文件编码（2026-09-14 实证踩坑）
- 症状：同一批文件里，`grep` 出来的中文有的正常、有的变成 `缁块煹瀹`（=「绿韵家」的 UTF-8 字节被当 GBK 解码），看上去像「线上文件是乱码老版」。
- **真相：文件本身是合法 UTF-8，乱码只是 Bash 工具在 Windows 下的终端解码假象**。本次据此差点得出「线上 index.html 是乱码，该用本地版覆盖它」的错误结论——若真推上去，会把线上 16 链接 / 5 任务卡片的完整导航页**降级**成本地 3 链接的旧版（回滚级事故）。
- 铁律：**任何「编码 / 乱码 / 是否损坏」的判断，一律用 Python 读字节复核**，不看 shell 的 grep/cat 输出：
  ```python
  b = open(p, 'rb').read()
  print(len(b), b.find('关键词'.encode('utf-8')))   # 命中 >0 即为合法 UTF-8
  ```
  再 `b.decode('utf-8')` 打印正文确认（Python 的 stdout 是 UTF-8，可信）。
- 推论：`gh api ... -q .content | base64 -d > x.html` 之后**不要用 grep 看中文**，改用 Read 工具或 Python。
- 顺带教训：**判定「本地比线上新」不能只看文件 mtime**。本次本地 index.html mtime(08-17) 晚于线上最后提交(08-13)，但内容明显更旧（副标题还写着「稳定托管（CloudStudio）」，是该主机迁移前的旧物）。判定方向应看：内容结构/落款日期/是否引用已废弃的托管方式，而非时间戳。

## 8. ⚠️ 同一文件不要在同一批次并行发多个 Edit —— 会**静默丢改动**（2026-09-17 实证）
- 症状：同一条消息里对**同一个文件**发 2 个 Edit，工具**都回** `Successfully edited file`，但其中一个改动**根本没落盘**。本次 `box specLock`（隐藏规格名2 整块）和 `id="specValRow1"` 两条都没进文件，只有同一批里另发的注释类改动生效了。
- 危害：回执是「成功」，极易直接进下一步验证/推送 —— 本次是靠**冒烟后的截图**看出水卡规格区还留着两个规格框，再 grep 回读才确认丢改动；若没截图就会把废稿推上线。
- 铁律：
  1. **同文件多改动一律串行**（一条 Edit 一个工具调用，等回执再发下一条）；并行只用于**不同文件**。
  2. 一批改动收尾时**用 Grep 回读关键 class/id 字符串**核验是否真的落盘，不看工具回执。
  3. 视觉类改动**必须靠真实渲染截图复核**（`regen_prd_shots.js` / `proto_smoke.js`），grep 只能证明字符串在、证不了效果对。

## 9. ⚠️ Windows .bat 脚本必须 GBK 编码 + CRLF 行尾（2026-09-17 实证）
- 症状：双击 bat，cmd 刷一堆 `'找' / '你' / '数字' / 'level' / 'off' 不是内部或外部命令`，脚本完全跑不起来。
- 根因：用 Write 工具写 `.bat` 默认产出 **LF（Unix）行尾 + UTF-8 编码**。Windows cmd 解析 **LF 行尾 + `if (` 括号块** 会错乱（`%errorlevel%` 被拆开当命令、中文行被当命令执行）；中文又按 GBK 读成乱码。
- 铁律：**.bat / .cmd 一律 GBK（cp936）编码 + CRLF 行尾**，并：
  - 首行加 `chcp 936 >nul`；
  - 避免 `if (...)` 括号块，改 `if errorlevel N goto label` / `goto` 结构；
  - 用 Python 落盘：`open(p,'wb').write(content.replace('\n','\r\n').encode('gbk'))`；
  - 校验：`b.count(b'\r\n')>0 and b.count(b'\n')-b.count(b'\r\n')==0 and bool(b.decode('gbk'))`。
- 注：纯 ASCII 的 bat（无中文、无括号块）用 LF 也能跑，所以旧脚本可能「碰巧没事」，一旦加中文/括号块就崩 —— 别据此认为编码无关。
- 相关：从 Bash 调 `cmd //c "x.bat"` 在 Git Bash 下路径会被转换（可能退化成交互模式）；要么用 PowerShell 工具跑，要么让用户双击。

## 10. ⚠️ headless Edge 里 `window.scrollTo()` 不派发 `scroll` 事件（2026-09-17 实证）
- 症状：headless 跑滚动相关断言时，元素明明已被 `window.scrollTo()` 移动（`getBoundingClientRect()` 值变了），但依赖 `scroll` 事件的重算逻辑（`window.addEventListener('scroll', fn, true)`）不触发 → 断言误判「逻辑未生效」。
- 真相：headless 无真实合成器，`scrollTo` 只改布局、**不派发 `scroll`**。**真实浏览器不受影响**（用户场景正常），纯属测试环境差异。
- 修法：测试探针里 `window.scrollTo(...)` 之后手动补一次 `window.dispatchEvent(new Event('scroll'))`，再等节流时间（30~50ms）后读断言值。

## 11. ⚠️ skill 备份仓库 ddyuan-spec/workbuddy-skills 必须 --branch main（2026-09-20 实证）
- 事实：skill 类文档备份仓库 = `ddyuan-spec/workbuddy-skills`（delivery-suite rules.json 已登记映射「skill 类文档」），只有 `main` 分支，**无 gh-pages**。
- 坑：`gh_push.py` 默认推 `gh-pages` 分支（为 Pages 交付设计），对 skill 仓库会全量 FAIL：`Branch gh-pages not found (HTTP 404)`。
- 正确用法：`python gh_push.py --repo ddyuan-spec/workbuddy-skills --branch main --root <skills根目录> --put "<skill相对路径>::<同远端路径>::<msg>"`；推完看 VERIFY 段 local=remote 逐文件对齐、结尾 ALL_OK。
- **数据结构约定（README 写明）**：仓库根目录直接放各 skill 独立文件夹（README 安装示例 `cp -r _tmp/<skill> ~/.workbuddy/skills/`），**不要**嵌套 `skills/` 或 `.workbuddy/skills/` 子目录；本地 `~/.workbuddy/skills/<name>` 与仓库根 `<name>` 一一对应。历史重复子目录已清，勿再建。
- **同步状态（2026-09-20 收尾）**：本地 39 个 user-level skill 已全部备份到根目录（含 6 个个人生活类 dating-coach / dating-talk / travel-cn / podcast-topic-picker / course-lecture-study / renqing-polish）。废弃的 `proto-suite` 已删，结构干净。
- 同步是**手动按需**的：改完 skill 不会自动备份，下次有重要 skill 改动后主动跑一次 `--spec-file` 增量补推即可。
- 注意仓库是 **Public**：私密 skill 内容公开可见；若要收回到私有仓库需另建 repo 并迁移（勿在 Public 仓动手改私密内容）。
