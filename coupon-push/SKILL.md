---
name: coupon-push
description: 泰小虎优惠券 · 独立推送 skill（队列驱动）。消费 核心业务/优惠券/.workbuddy/push-queue.json 中 state=MERGED_READY 的任务，按 FIFO 一条条推送；每条推送前做范围/红字/待确认预检，推送后做健康检查（线上回读一致 + PRD 红字=0 + 结构完整 + 原型关键 JS 函数仍在），发现阻断问题立即停下找用户确认，绝不静默发布。与 coupon-req-flow 解耦——合并只产出本地已转黑的正式文件并登记队列，本 skill 负责发布。由用户另开任务执行。
agent_created: true
---

# coupon-push · 优惠券独立推送 skill（队列驱动 · 可确认 · 推完检查）

> 与 `coupon-req-flow` 解耦（2026-08-08 起）：合并流程只把草稿合入正式源文件 + 整篇转黑，并向 `push-queue.json` 登记一条 `MERGED_READY`；本 skill 消费队列、把本地已合并的正式文件发布到 GitHub Pages，且**每条推完做健康检查、出问题找用户确认**。

## 何时用

- 用户说「推送优惠券」「推 GitHub Pages」「把合并好的发上去」「coupon-push 跑一下」「你们一个个推送上去」「把没推的任务一条条推了」。
- 多任务并行合并后，一次性按队列顺序发布，并逐条确认健康。

## 关键不变量（红线）

- **只推送「已合并到正式文件」的内容**；不编辑正式文件、不创作需求、不推送 `tasks/` 草稿。
- **队列驱动**：凭 `push-queue.json` 的 `MERGED_READY` 记录决定推什么，不靠记忆、不靠猜。
- **逐条 FIFO + 遇阻断即停**：任一任务预检/推送后校验失败 → 该任务及后续全部停下，精确报问题，找用户确认；绝不静默发布或跳过错的继续。
- **不推送含红字（未转黑）的正式文件**，不推送非优惠券文件。
- **不自行修改需求内容**：本 skill 只发布，发现问题只报告 + 问，不动笔改 PRD/原型。

## 防漏推硬门禁（三板斧 · 反复踩坑固化）

> 真实「漏推」几乎都长这样：**git 源已 `PUT` 成功、`raw.githubusercontent` 回读也对，但用户打开 `ddyuan-spec.github.io` 仍是旧内容**——因为 `contents` API 的 `PUT` **不自动触发 Pages 重建**，站点停留旧构建 + CDN/浏览器缓存。以下三条是防漏推的硬门禁，**违反任一条即视为流程失败**：

1. **只凭队列推，不凭记忆**：推什么只看 `push-queue.json` 的 `MERGED_READY`；合并流程没登记 → 永不推送。
2. **Pages 不 `built` 不算成功**：全部文件 `PUT` 后，**必须 `POST /pages/builds` 并轮询到最新一条 `status=built`**；在此之前**禁止**把 entry 标 `PUSHED`、**禁止**对用户说「已推送 / 线上已更新」，只能说「git 源已更新，等待 Pages 重建」。build 失败（`errored`/超时）→ entry 维持 `MERGED_READY` 或标 `NEEDS_CONFIRM`，并明确告知「线上仍是旧版」。
3. **终点再验真页面**：`built` 后，直接请求线上 `https://ddyuan-spec.github.io/taixiaohu/<remotePath>`（**不是 raw**），确认本次新增的关键内容串已出现；缺失即 Pages 未真正刷新 → `NEEDS_CONFIRM` + 提示清缓存 / 重试重建。

## 状态文件（位于 核心业务/优惠券/.workbuddy/）

### push-queue.json（推送队列）
```json
{
  "version": 1,
  "entries": [
    {
      "taskId": "2026-08-08-share-inviter-backend-note",
      "title": "分享活动·后台变更不触发发券·特别说明",
      "files": ["优惠券体系新需求PRD.html"],
      "state": "MERGED_READY",
      "mergedAt": "2026-08-08T10:12:00",
      "pushedAt": null,
      "remoteSha": null,
      "note": "本地 PRD 三处已补说明并转黑，待推送"
    }
  ]
}
```
- `state`：`MERGED_READY`（已合并待推）/ `PUSHED`（已推）/ `NEEDS_CONFIRM`（预检或校验失败，等用户拍板）。
- **写入方**：`coupon-req-flow` 步骤 8 合并完即追加一条 `MERGED_READY`（文件不存在则新建）。
- **消费方**：本 skill 把 `MERGED_READY` 处理完改为 `PUSHED`；出问题改为 `NEEDS_CONFIRM` 并 `note` 写清原因。

### push-log.json（每文件末次推送指纹，用于漂移检测）
```json
{
  "version": 1,
  "files": {
    "平台端后台原型.html": {"remotePath": "coupon-platform.html", "lastPushedSha": null, "lastPushedAt": null},
    "优惠券体系新需求PRD.html": {"remotePath": "coupon-prd.html", "lastPushedSha": null, "lastPushedAt": null},
    "coupon-relate-live.html": {"remotePath": "coupon-relate-live.html", "lastPushedSha": null, "lastPushedAt": null},
    "coupon-rule-autogen.html": {"remotePath": "coupon-rule-autogen.html", "lastPushedSha": null, "lastPushedAt": null}
  }
}
```
- 每次成功推送某文件后，用 GitHub 返回的 `content.sha`（**git blob SHA1，40 位十六进制**，即 `sha1("blob "+len(content)+"\0"+content)`）回填 `lastPushedSha` + `lastPushedAt`。
- 用于「漂移检测」安全网：队列清空后，用**相同的 git blob SHA1 算法**算本地文件指纹，与 `lastPushedSha` 比对；若 ≠ `lastPushedSha` 且该文件本轮未被推送 → 说明有未记录的本地改动，停下找用户确认，**不自动推**。**⚠️ 算法必须一致**：`lastPushedSha` 是 SHA1，不要误用 `sha256` 去比（否则每个文件都会永久误报「漂移」）。Python 算法：`h=hashlib.sha1(); h.update(b"blob "+str(len(content)).encode()+b"\0"+content); h.hexdigest()`。

## 文件 → 远程映射（仓库 ddyuan-spec/taixiaohu，根目录短链）

| 本地源文件 | remotePath | 线上地址 |
|---|---|---|
| 核心业务/优惠券/平台端后台原型.html | coupon-platform.html | https://ddyuan-spec.github.io/taixiaohu/coupon-platform.html |
| 核心业务/优惠券/优惠券体系新需求PRD.html | coupon-prd.html | https://ddyuan-spec.github.io/taixiaohu/coupon-prd.html |
| 核心业务/优惠券/coupon-relate-live.html | coupon-relate-live.html | https://ddyuan-spec.github.io/taixiaohu/coupon-relate-live.html |
| 核心业务/优惠券/coupon-rule-autogen.html | coupon-rule-autogen.html | https://ddyuan-spec.github.io/taixiaohu/coupon-rule-autogen.html |

> 用户可在调用时指定只推某些任务/文件；不指定则处理队列中全部 `MERGED_READY`。

## 四避坑（gh api PUT，强制，跨平台）

> ⚠️ **本节「推送片段」已废弃**：实际推送由 `scripts/push_queue.py` → `gh_push.py` 完成，不要再手抄下面的 `gh api PUT` 片段（见上方「推送引擎已脚本化」）。保留本节仅为说明底层避坑原理。

1. **ARG_MAX**：base64 绝不作文命令行参数 → 用 `gh api -X PUT ... --input body.json`。
2. **临时文件路径**：`--input` 文件放**当前工作目录**相对路径（如 `./ghbody_tmp.json`），gh.exe 不认 `/tmp/`。
3. **404 污染 sha**：用退出码判断旧 sha 是否存在（见下片段），勿把错误 JSON 当 sha。
4. **代理**：命令前 `HTTPS_PROXY=""`；base64 用 `base64 -w0`（**若环境无 `base64` CLI，改 `python -c "import base64,sys;print(base64.b64encode(open(f,'rb').read()).decode())"` 生成 body.json**）；校验用 `https://raw.githubusercontent.com/ddyuan-spec/taixiaohu/main/<remotePath>`（无 Pages CDN 缓存）。
5. **Windows 环境坑（实测）**：① 本机 `base64` / `stat` CLI 均不存在，base64 用 Python、mtime 用 `python -c "import os;print(os.path.getmtime(p))"`；② 本机 Python 是 **Windows 版**，不认 `/c/Users/...` 这种 Git Bash 风格绝对路径，绝对路径必须用 `C:/Users/...`（或相对路径）；③ `gh api` 推/取内容均正常，`raw.githubusercontent.com` 偶发 `ConnectionResetError`，失败重试或改用 `gh api contents` 取 base64 再解码。

### 推送片段（在 核心业务/优惠券/ 目录下执行）
```bash
cd "/c/Users/13364/WorkBuddy/泰小虎/核心业务/优惠券"
FILE="优惠券体系新需求PRD.html"          # 本地源文件名
REMOTE="coupon-prd.html"                # 远程路径
B64=$(base64 -w0 "$FILE")
if HTTPS_PROXY="" gh api repos/ddyuan-spec/taixiaohu/contents/$REMOTE -q .sha > sha.txt 2>/dev/null; then
  SHA=$(cat sha.txt); else SHA=""; fi
if [ -n "$SHA" ]; then
  printf '{"message":"chore: push %s via coupon-push","content":"%s","sha":"%s"}' "$FILE" "$B64" "$SHA" > ghbody_tmp.json
else
  printf '{"message":"chore: push %s via coupon-push","content":"%s"}' "$FILE" "$B64" > ghbody_tmp.json
fi
HTTPS_PROXY="" gh api -X PUT repos/ddyuan-spec/taixiaohu/contents/$REMOTE --input ./ghbody_tmp.json
rm -f ghbody_tmp.json sha.txt
```

## 执行流程

1. **载入队列**：读 `push-queue.json`。文件缺失/无 `MERGED_READY` → 报告「没有待推送任务」并进入漂移检测（步骤 6）。
2. **排序**：取 `state==MERGED_READY` 的 entries，按 `mergedAt` 升序（FIFO）。
3. **逐条处理（循环）**：对每条 entry:
   - **预检**（见下「预检清单」）：扫该 entry `files` 涉及的本地正式文件。
     - 若发现阻断项（红字残留 / 未消 `待确认` / 与在途任务重叠）→ 该 entry 改 `NEEDS_CONFIRM`、写 `note`，**立即停下整个队列**，跳到步骤 8 报告并找用户确认。
   - **去重推送**：本 run 已推过的文件不再推；对本 entry 未推的文件逐个推（片段见上）。
   - **git 源层健康检查**（见下「健康检查清单」）：用 `raw.githubusercontent.com/.../main/<remotePath>` 回读与本地比对、红字=0、结构完整、原型关键 JS 函数仍在。
     - 失败 → 该 entry（及同文件的其他 entry）改 `NEEDS_CONFIRM`、写 `note`，**立即停下整个队列**，跳步骤 8。
   - 通过 → 暂存「git 源已更新」，但**此刻不写 `PUSHED`**（等步骤 4.5 / 4.6 全绿）。
4. **暂存 git 指纹**：把本轮已推文件的 `remoteSha` 记下，entry 仍保持 `MERGED_READY`（待 4.5 / 4.6 通过再翻 `PUSHED`）。
4.5. **强制触发 Pages 重建（硬门禁，必做）**：全部文件 `PUT` 完成后，执行一次 `gh api -X POST repos/ddyuan-spec/taixiaohu/pages/builds` 触发 GitHub Pages 重建。**`contents` API 的 `PUT` 不会自动触发 Pages 构建**——跳过本步，线上站点停留旧构建 + CDN/浏览器缓存，用户打开仍是旧内容（即「漏推」假象的 root cause）。轮询 `GET /repos/ddyuan-spec/taixiaohu/pages/builds` 直到最新一条 `status=built`（约 1–2 分钟）。
   - ⚠️ **硬门禁**：`status=built` **之前**，禁止把任何 entry 标 `PUSHED`、禁止对用户说「已推送 / 线上已更新」；只能说「git 源已更新，等待 Pages 重建」。
   - `errored` 或长时间 `building` → 本 run 所有 entry **维持 `MERGED_READY`**（或标 `NEEDS_CONFIRM`），明确告知用户「git 已更新但 Pages 重建失败，线上仍是旧版」，**绝不说「已推送成功」**。
4.6. **Pages 层终验（硬门禁）**：`built` 后，对每条 entry 的远程文件**直接请求线上 `https://ddyuan-spec.github.io/taixiaohu/<remotePath>`（不是 raw）**，确认页面含本次新增的关键内容串（如新章节标题 / 按钮文案）。缺失 → 视为 Pages 未真正刷新，entry 标 `NEEDS_CONFIRM` 并提示清缓存 / 重试重建。
5. **写回状态（仅 4.5+4.6 全绿后）**：把本 run 处理的 entry 改为 `PUSHED`，回填 `pushedAt` + `remoteSha`；`push-log.json` 各文件 `lastPushedSha/At` 更新。**未通过 4.5 / 4.6 的 entry 一律不写 `PUSHED`。**
6. **漂移检测（安全网）**：遍历 `push-log.json` 的已知文件，**用 git blob SHA1 算法**（见上 `push-log.json` 段）算本地指纹；若 ≠ `lastPushedSha` 且该文件本轮未被推送 → 说明有「未登记本地改动」。停下，报告具体文件 + 差异提示，找用户确认是否要补推（**不自动推**）。
7. **记日志**：向 `核心业务/优惠券/.workbuddy/memory/YYYY-MM-DD.md` 追加本次推送记录（推了哪些文件、URL、是否遇阻、Pages built 时间）。
8. **汇总（最终对外报告）**：**仅在 4.5+4.6 全绿后**，才对用户说「✅ 已推送并线上生效」并给出 URL；若中途有 `NEEDS_CONFIRM`，精确说明哪条 / 哪个文件 / 哪项检查 / 哪段内容，等用户拍板（修复后重跑 / 跳过该条 / 终止）。

## 预检清单（每条 entry 推送前）

- **红字残留**：本地正式文件 `color:#d32f2f`（不区分大小写）计数应为 0；>0 即阻断。
- **待确认悬空**：`待确认` 计数；>0 即阻断（合并流程要求合并前清零）。
- **重叠冲突**：扫 `核心业务/优惠券/tasks/` 下各任务 `SCOPE.md`，若本 entry 文件/章节与**仍在途（未合并）**任务范围重叠 → 阻断，列出双方范围找用户确认。
- **PRD 截图同步检查（SHOT-SYNC）**：对 entry.files 中每个 PRD 文件，提取其引用的本地 `coupon-prd-assets/*.png`；若本次 entry 同时包含「原型 HTML 文件」（如 `平台端后台原型.html`），取这些原型文件的最新 mtime 为 `M`，逐个比对：**任一 png 的 mtime < M → 该 PRD 截图未同步重截 → 阻断**，提示「<png名> 早于原型修改时间，请先用 proto-c / proto-admin 的 `PROTO-SHOT-001` 重截再推（脚本 `scripts/regen_prd_shots.js`）」。仅推 PRD 且原型未改动（entry.files 无原型文件）时不触发此检查（原型没动，截图无需动）。
  - 检测可走轻量：用 Python `os.path.getmtime` 取 png 与原型 mtime 比较；或在 Git Bash 用 `stat -c %Y`。

## 健康检查清单（每条推送后 · 轻量必查 + 异常升级）

**轻量必查（每次都跑）**：
- **回读一致**：`raw.githubusercontent.com/.../main/<remotePath>` 下载后与本地文件 `cmp` 字节一致（不一致 → 阻断）。
- **PRD 红字=0**：线上内容 `#d32f2f` 计数 0。
- **结构完整**：用 Python `html.parser` 解析，标签开合平衡、无未闭合 `<script>`/`<style>`、`<head><body>` 均在。
- **原型关键 JS 函数仍在**（仅原型文件）：确认 `autoGenRule` 等关键函数名仍存在（来自 coupon-spec 约定的自动生成规则函数）；`<script>` 开合计数平衡。
- **待确认=0**：线上内容 `待确认` 计数 0。

**异常升级（轻量可疑时跑）**：
- 轻量任一项「可疑但未直接阻断」（如标签轻微不平衡、关键函数疑似改名）→ 调用 `prd-suite` / `proto-c / proto-admin` 跑完整结构门禁与冒烟，拿详细诊断再决定阻断 or 放行，并报告用户。

> 设计取舍：默认轻量快检，保证「一条条推」的节奏；仅在可疑时升级完整套件，避免每次都重跑耗时。

## 与 coupon-req-flow 的契约

- 合并操作员在**步骤 8 收尾**时，向 `push-queue.json` 追加一条 `MERGED_READY`（含 `taskId`/`files`/`mergedAt`）。任务目录 `tasks/{id}/` 删不删都不影响队列（状态已外置）。
- 本 skill 不依赖 `tasks/` 是否存在，只认 `push-queue.json` + `push-log.json`。
- 两者通过这两个文件解耦，可跨会话 / 跨任务稳定协作。

## 复用现有 skill

- 推送底层四避坑同 `delivery-suite`。
- 异常升级时调用 `prd-suite`（含 `prd-structure-checker`）、`proto-c / proto-admin`。

## ⚠️ 推送引擎已脚本化（禁止重写临时脚本）

**硬门禁（类比 delivery-suite 的 DLV-PUSH-011）**：推送一律走 `scripts/push_queue.py`，它消费 `push-queue.json` 的 `MERGED_READY`、按 FIFO 处理，并把实际的 `gh api PUT` + Pages 重建 + 真页验真 **委托给 `delivery-suite/scripts/gh_push.py`**。**不要再手写下面「推送片段」里的 `gh api PUT` 临时脚本**（那是历史遗留，已被 `push_queue.py` 取代）；也不要新建 `_push_*.py`。

- 常规用法：`python scripts/push_queue.py --dry-run`（先预演）→ 确认无误去掉 `--dry-run` 实推。
- 新增能力需求（如特殊校验/新仓库）→ **扩展 `gh_push.py`**，不要另写脚本。
- 预检语义：红字 `#d32f2f` 残留 = 硬阻断；「待确认」默认仅告警（本项目常由用户主动保留），加 `--strict` 恢复硬阻断。
- `push_queue.py` 已内建：队列驱动、FIFO、遇阻即停（置 `NEEDS_CONFIRM`）、`--wait-pages` 重建门禁、`--keyword` 真页验真、推送后回填 `remoteSha` 供漂移检测、运行末跑漂移安全网。
