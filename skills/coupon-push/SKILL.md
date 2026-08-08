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
- 每次成功推送某文件后，用 GitHub 返回的 `content.sha`（或回读 raw 算 sha）回填 `lastPushedSha` + `lastPushedAt`。
- 用于「漂移检测」安全网：队列清空后，若某已知文件本地 sha ≠ `lastPushedSha` → 说明有未记录的本地改动，停下找用户确认，**不自动推**。

## 文件 → 远程映射（仓库 ddyuan-spec/taixiaohu，根目录短链）

| 本地源文件 | remotePath | 线上地址 |
|---|---|---|
| 核心业务/优惠券/平台端后台原型.html | coupon-platform.html | https://ddyuan-spec.github.io/taixiaohu/coupon-platform.html |
| 核心业务/优惠券/优惠券体系新需求PRD.html | coupon-prd.html | https://ddyuan-spec.github.io/taixiaohu/coupon-prd.html |
| 核心业务/优惠券/coupon-relate-live.html | coupon-relate-live.html | https://ddyuan-spec.github.io/taixiaohu/coupon-relate-live.html |
| 核心业务/优惠券/coupon-rule-autogen.html | coupon-rule-autogen.html | https://ddyuan-spec.github.io/taixiaohu/coupon-rule-autogen.html |

> 用户可在调用时指定只推某些任务/文件；不指定则处理队列中全部 `MERGED_READY`。

## 四避坑（gh api PUT，强制，跨平台）

1. **ARG_MAX**：base64 绝不作文命令行参数 → 用 `gh api -X PUT ... --input body.json`。
2. **临时文件路径**：`--input` 文件放**当前工作目录**相对路径（如 `./ghbody_tmp.json`），gh.exe 不认 `/tmp/`。
3. **404 污染 sha**：用退出码判断旧 sha 是否存在（见下片段），勿把错误 JSON 当 sha。
4. **代理**：命令前 `HTTPS_PROXY=""`；base64 用 `base64 -w0`；校验用 `https://raw.githubusercontent.com/ddyuan-spec/taixiaohu/main/<remotePath>`（无 Pages CDN 缓存）。

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

1. **载入队列**：读 `push-queue.json`。文件缺失/无 `MERGED_READY` → 报告「没有待推送任务」并进入漂移检测（步骤 9）。
2. **排序**：取 `state==MERGED_READY` 的 entries，按 `mergedAt` 升序（FIFO）。
3. **逐条处理（循环）**：对每条 entry:
   - **预检**（见下「预检清单」）：扫该 entry `files` 涉及的本地正式文件。
     - 若发现阻断项（红字残留 / 未消 `待确认` / 与在途任务重叠）→ 该 entry 改 `NEEDS_CONFIRM`、写 `note`，**立即停下整个队列**，跳到步骤 8 报告并找用户确认。
   - **去重推送**：本 run 已推过的文件不再推；对本 entry 未推的文件逐个推（片段见上）。
   - **推送后健康检查**（见下「健康检查清单」）：回读 raw 与本地比对、红字=0、结构完整、原型关键 JS 函数仍在。
     - 失败 → 该 entry（及同文件的其他 entry）改 `NEEDS_CONFIRM`、写 `note`，**立即停下整个队列**，跳步骤 8。
   - 全部通过 → entry 改 `PUSHED`，回填 `pushedAt` + `remoteSha`，并把该文件在 `push-log.json` 的 `lastPushedSha/At` 更新。
4. **更新状态**：把 `push-queue.json` / `push-log.json` 写回。
5. **漂移检测（安全网，步骤 3 之后）**：遍历 `push-log.json` 的已知文件，对本地文件算 sha256；若 ≠ `lastPushedSha` 且该文件本轮未被推送 → 说明有「未登记本地改动」。停下，报告具体文件 + 差异提示，找用户确认是否要补推（**不自动推**）。
6. **记日志**：向 `核心业务/优惠券/.workbuddy/memory/YYYY-MM-DD.md` 追加本次推送记录（推了哪些文件、URL、是否遇阻）。
7. **汇总**：给用户列出每条任务的处理结果（PUSHED 的 URL / NEEDS_CONFIRM 的原因）。
8. **遇阻报告**：若中途停下，用 AskUserQuestion 或文字精确说明——哪条任务、哪个文件、哪项检查、哪段内容出问题；等用户拍板（修复后重跑 / 跳过该条 / 终止）。

## 预检清单（每条 entry 推送前）

- **红字残留**：本地正式文件 `color:#d32f2f`（不区分大小写）计数应为 0；>0 即阻断。
- **待确认悬空**：`待确认` 计数；>0 即阻断（合并流程要求合并前清零）。
- **重叠冲突**：扫 `核心业务/优惠券/tasks/` 下各任务 `SCOPE.md`，若本 entry 文件/章节与**仍在途（未合并）**任务范围重叠 → 阻断，列出双方范围找用户确认。

## 健康检查清单（每条推送后 · 轻量必查 + 异常升级）

**轻量必查（每次都跑）**：
- **回读一致**：`raw.githubusercontent.com/.../main/<remotePath>` 下载后与本地文件 `cmp` 字节一致（不一致 → 阻断）。
- **PRD 红字=0**：线上内容 `#d32f2f` 计数 0。
- **结构完整**：用 Python `html.parser` 解析，标签开合平衡、无未闭合 `<script>`/`<style>`、`<head><body>` 均在。
- **原型关键 JS 函数仍在**（仅原型文件）：确认 `autoGenRule` 等关键函数名仍存在（来自 coupon-spec 约定的自动生成规则函数）；`<script>` 开合计数平衡。
- **待确认=0**：线上内容 `待确认` 计数 0。

**异常升级（轻量可疑时跑）**：
- 轻量任一项「可疑但未直接阻断」（如标签轻微不平衡、关键函数疑似改名）→ 调用 `prd-suite` / `proto-suite` 跑完整结构门禁与冒烟，拿详细诊断再决定阻断 or 放行，并报告用户。

> 设计取舍：默认轻量快检，保证「一条条推」的节奏；仅在可疑时升级完整套件，避免每次都重跑耗时。

## 与 coupon-req-flow 的契约

- 合并操作员在**步骤 8 收尾**时，向 `push-queue.json` 追加一条 `MERGED_READY`（含 `taskId`/`files`/`mergedAt`）。任务目录 `tasks/{id}/` 删不删都不影响队列（状态已外置）。
- 本 skill 不依赖 `tasks/` 是否存在，只认 `push-queue.json` + `push-log.json`。
- 两者通过这两个文件解耦，可跨会话 / 跨任务稳定协作。

## 复用现有 skill

- 推送底层四避坑同 `delivery-suite`。
- 异常升级时调用 `prd-suite`（含 `prd-structure-checker`）、`proto-suite`。
