---
name: coupon-push
description: 泰小虎优惠券 · 独立推送 skill。把已合并到正式的优惠券文件（平台端原型 coupon-platform.html、主 PRD 优惠券体系新需求PRD.html，及按需的 coupon-relate-live.html / coupon-rule-autogen.html 等）逐个推送到 GitHub Pages（ddyuan-spec/taixiaohu 仓库根目录短链）。每次只推一个文件、按顺序、推送前范围冲突预检、推送后回读校验。与 coupon-req-flow 解耦——合并只产出本地已转黑的正式文件，本 skill 负责发布。由用户另开任务执行。
---

# coupon-push · 优惠券独立推送 skill

> 与 `coupon-req-flow` 解耦（2026-08-08 起）：合并流程只把草稿合入正式源文件并整篇转黑，**不推送**；本 skill 负责把本地已合并的正式文件发布到 GitHub Pages。用户另开一个任务执行本 skill，逐个推送已就绪的正式文件。

## 何时用

- 用户说「推送优惠券」「推 GitHub Pages」「把合并好的发上去」「coupon-push 跑一下」「你们一个个推送上去」等。
- 多任务并行合并后，一次性把本地累积的正式文件改动顺序发布。

## 推送目标（仓库 ddyuan-spec/taixiaohu，根目录短链）

| 本地源文件 | 线上地址 |
|---|---|
| 核心业务/优惠券/平台端后台原型.html | https://ddyuan-spec.github.io/taixiaohu/coupon-platform.html |
| 核心业务/优惠券/优惠券体系新需求PRD.html | https://ddyuan-spec.github.io/taixiaohu/coupon-prd.html |
| 核心业务/优惠券/coupon-relate-live.html | https://ddyuan-spec.github.io/taixiaohu/coupon-relate-live.html |
| 核心业务/优惠券/coupon-rule-autogen.html | https://ddyuan-spec.github.io/taixiaohu/coupon-rule-autogen.html |

> 用户每次执行可指定要推哪些文件；不指定则默认推 `coupon-platform.html` + `优惠券体系新需求PRD.html`。

## 四避坑（gh api PUT，强制）

1. **ARG_MAX**：base64 绝不能作 `-f content="$b64"` 命令行参数（超系统参数长度上限报 `Argument list too long`）→ 改用 `gh api -X PUT ... --input body.json`（body.json 含 `{"message":"...","content":"<base64>","sha":"<旧sha>?"}`）。
2. **临时文件路径**：`--input` 的文件路径 gh.exe(Windows 原生) 不认 Unix `/tmp/` → 必须放**当前工作目录**用相对路径（如 `./ghbody_tmp.json`）。
3. **404 污染**：文件不存在时 `gh api -q .sha` 会把错误 JSON 赋给变量 → 用退出码判断：`if HTTPS_PROXY="" gh api ... -q .sha > sha.txt 2>/dev/null; then sha=$(cat sha.txt); else sha=""; fi`（存在→更新带 sha，不存在→新建不带 sha）。
4. **代理**：命令前加 `HTTPS_PROXY=""` 绕过代理；base64 用 `base64 -w0`；验证用 `https://raw.githubusercontent.com/ddyuan-spec/taixiaohu/main/<path>`（无 Pages CDN 缓存）。

## 执行流程（逐文件循环）

1. 对本次要推的每个文件，依次执行 2–6（**一个一个推，不并发**）。
2. 读本地正式源文件最新字节 → `base64 -w0` 编码 → 写入当前工作目录 `./ghbody_tmp.json`（先拼 JSON：`{"message":"chore: push <file> via coupon-push","content":"<b64>"}`，若有 sha 则追加 `"sha":"<sha>"`）。
3. 查旧 sha（退出码判断 404，见避坑 3）。
4. `HTTPS_PROXY="" gh api -X PUT repos/ddyuan-spec/taixiaohu/contents/<path> --input ./ghbody_tmp.json`。
5. 推送后回读 `https://raw.githubusercontent.com/ddyuan-spec/taixiaohu/main/<path>`，校验：关键新内容已落地、且 `d32f2f` 红字残留应为 0。
6. 记录该文件推送结果（成功 / 失败 + 线上 URL），继续下一个。
7. 全部完成后汇总推送清单给用户（文件、URL、是否成功）。

## 前置冲突预检（建议跑）

- 推送前扫 `核心业务/优惠券/tasks/` 下各任务 `SCOPE.md`，确认本次推送的正式文件未被在途任务同时改动；若发现重叠且未确认，停下找用户确认，不静默覆盖。

## 红线

- 本 skill **只推送「已合并到正式文件」的内容**；不编辑正式文件、不创作需求、不推送 `tasks/` 草稿。
- 逐文件推送、逐个校验；任一文件推送失败立即停下报告，不跳过继续。
- 不推送非优惠券文件；不推送含红字（未转黑）的正式文件。
