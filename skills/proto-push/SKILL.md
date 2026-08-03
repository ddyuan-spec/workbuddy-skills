---
name: proto-push
description: 将 PRD / 前端原型 HTML 推送到 GitHub Pages 预览（ddyuan-spec 仓库）。把本地 HTML 文件通过 gh api PUT 推送为仓库根目录文件，生成短链 https://ddyuan-spec.github.io/<repo>/<file>.html。覆盖三大避坑：① base64 不得作命令行参数（ARG_MAX 超限 / Git Bash 静默截断）→ 用 Python 生成 body.json；② 临时文件放当前工作目录（gh.exe 不认 /tmp）；③ 404 污染 sha → 用退出码判断是否存在。推送后必须用 raw.githubusercontent 验证内容含新内容。触发词：推 GitHub、发线上链接、改完推 GitHub、GitHub Pages、推送原型、短链、上线预览。
agent_created: true
---

# 原型 / PRD 推送 GitHub Pages（proto-push）

## 用途
把本地单文件 HTML（PRD / 四端原型 / 平铺评审板）推送到 GitHub Pages 仓库，获得可分享的线上短链。

## 适用仓库
- 优惠券 / 泰小虎类需求：`ddyuan-spec/taixiaohu`（根目录短链，如 `https://ddyuan-spec.github.io/taixiaohu/coupon-prd.html`）
- skill 类文档：`ddyuan-spec/workbuddy-skills`
- 其它 GitHub Pages 仓库按 owner/repo 替换

## 强制流程（四步）

### 1. 准备文件与 base64 —— 永远用 Python 生成 body.json
**禁止**把 base64 作为命令行参数（Windows Git Bash 下超长 base64 会静默截断，导致 GitHub 收到旧内容/空内容，极具迷惑性）。临时文件必须放**当前工作目录**（相对路径 `./body.json`），因为 gh.exe 是 Windows 原生程序，不认 Unix `/tmp/...`。

```python
import base64, json, subprocess
f = "优惠券体系新需求PRD.html"        # 要推送的本地文件
repo = "ddyuan-spec/taixiaohu"
path = "coupon-prd.html"               # 仓库根目录的目标文件名（根目录短链）
b = base64.b64encode(open(f, 'rb').read()).decode()
# 查旧 sha：存在→更新带 sha；不存在→新建不带 sha。用退出码判断，避开 404 把错误 JSON 赋给变量
r = subprocess.run('HTTPS_PROXY="" gh api repos/%s/contents/%s -q .sha' % (repo, path),
                   shell=True, capture_output=True, text=True)
sha = r.stdout.strip() if (r.returncode == 0 and r.stdout.strip()) else ""
body = {"message": "chore: push %s" % path, "content": b}
if sha:
    body["sha"] = sha
json.dump(body, open("body.json", "w"))
print("sha=", sha, "b64_len=", len(b))
```

### 2. 推送（gh api PUT --input body.json）
命令前加 `HTTPS_PROXY=""` 绕过代理：

```bash
HTTPS_PROXY="" gh api -X PUT repos/ddyuan-spec/taixiaohu/contents/coupon-prd.html --input body.json
```

### 3. 验证（必须做，防止"看起来推送了其实没更新"）
用 `raw.githubusercontent.com` 验证（无 Pages CDN 缓存）：

```bash
curl -s https://raw.githubusercontent.com/ddyuan-spec/taixiaohu/main/coupon-prd.html | grep -c "V2.0"
```

确认新内容（如版本号、新增章节标题）确实出现在 raw 中。**仅看 gh api 返回 200 / commit sha 更新不足以证明内容已变**——base64 截断时 sha 也会"更新"但内容没变。

### 4. 清理临时文件
推送并验证后删除 `body.json`（及任何 `_push_*.py` / `b64.txt` 临时脚本），避免污染工作区。

## 红线（多次踩坑固化）
- ❌ **绝不用** `printf '{"content":"%s"}' "$(cat b64.txt)"` 或 `echo "$(cat b64)"` 把超长 base64 展开为命令行参数（ARG_MAX 超限 / Git Bash 静默截断）。
- ❌ **绝不用** `/tmp/...` 作为 `--input` 文件路径（gh.exe 找不到 → 读不到 body）。
- ❌ 推送后**不验证**直接告知用户"已上线"。
- ✅ 404 污染：文件不存在时 `gh api -q .sha` 会把错误 JSON 赋给变量 → 改用退出码判断（见步骤1 的 `if r.returncode==0`）。

## 与 requirement-workflow / prd-structure-checker 的关系
定版 PRD / 原型确认后，用本 skill 推送 GitHub Pages 生成短链交付；推送前须先过 prd-structure-checker 结构排查（prd-structure-checker skill）。
