# -*- coding: utf-8 -*-
"""
push_queue.py — coupon-push 队列驱动推送封装（复用 gh_push.py，不重写临时脚本）

消费 push-queue.json 中 state=MERGED_READY 的任务，按合并时间 FIFO 一条条发布；
实际「推 GitHub / 触发 Pages 重建 / 真页验真」全部委托给
  ../delivery-suite/scripts/gh_push.py
本脚本只保留 coupon-push 的领域逻辑：队列驱动、FIFO、预检、遇阻即停、状态机、漂移检测。

用法
----
  python push_queue.py [--queue Q] [--dry-run] [--keyword K] [--only TASKID] [--no-wait-pages]

默认：
  --queue  ~/.workbuddy/.../优惠券/.workbuddy/push-queue.json （自动探测失败则回退常量）
  --root   由 queue 路径推导（queue 的上上级目录 = 优惠券目录）
推送引擎 gh_push.py：兄弟 skill ../delivery-suite/scripts/gh_push.py

不变量（与 SKILL.md 一致）
-------------------------
- 只推 MERGED_READY；FIFO；任一预检/推送失败 → 该条及后续全停，改 NEEDS_CONFIRM。
- Pages 不 built 不算成功（--wait-pages 强制重建+轮询）；可选 --keyword 做真页验真。
- 推送后写回 PUSHED + pushedAt + remoteSha（供漂移检测）；push-log.json 同步更新。
- 脚本不自改自身；若某次需求超出 gh_push.py 能力，反馈后由 AI 在当回合扩展 gh_push.py。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = "ddyuan-spec/taixiaohu"
BRANCH = "main"
DEFAULT_QUEUE = r"C:/Users/13364/WorkBuddy/泰小虎/核心业务/优惠券/.workbuddy/push-queue.json"


def gh_push_path():
    here = os.path.dirname(os.path.abspath(__file__))
    # scripts/ 的兄弟 skill：上溯两级到 skills/，再进 delivery-suite/scripts/
    return os.path.normpath(os.path.join(here, "..", "..", "delivery-suite", "scripts", "gh_push.py"))


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def git_blob_sha1(path):
    """与 GitHub blob SHA1 一致：sha1('blob '+len+'\0'+content)。用于漂移检测。"""
    try:
        data = open(path, "rb").read()
    except FileNotFoundError:
        return None
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode() + b"\0" + data)
    return h.hexdigest()


def precheck(root, files, strict=False):
    """返回 (block_reasons, warn_reasons)。
    红字 #d32f2f（不区分大小写）是硬契约 → 阻断。
    「待确认」本项目常由用户主动保留（见队列历史 note）→ 默认仅告警；
    加 --strict 则恢复 SKILL 原文的硬阻断语义。
    """
    block, warn = [], []
    for rel in files:
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            block.append(f"文件不存在: {rel}")
            continue
        try:
            txt = open(full, "r", encoding="utf-8", errors="ignore").read()
        except Exception as e:
            block.append(f"读取失败 {rel}: {e}")
            continue
        red = txt.lower().count("#d32f2f")
        todo = txt.count("待确认")
        if red > 0:
            block.append(f"{rel}: 红字(#d32f2f) 残留 {red} 处")
        if todo > 0:
            msg = f"{rel}: 待确认 残留 {todo} 处"
            (block if strict else warn).append(msg)
    return block, warn


def remote_for(push_log, rel):
    """本地名 → 远端路径：优先 push-log.json 映射，否则用基线名（去掉目录）。"""
    entry = push_log.get("files", {}).get(rel)
    if entry and entry.get("remotePath"):
        return entry["remotePath"]
    return os.path.basename(rel)


def fetch_remote_sha(repo, branch, remote, env):
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{remote}?ref={branch}", "-q", ".sha"],
        capture_output=True, env=env, shell=True,
    )
    out = (r.stdout or b"").decode("utf-8", "replace").strip()
    return out if r.returncode == 0 and len(out) == 40 else None


def build_env():
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env["HTTP_PROXY"] = ""
    env["HTTPS_PROXY"] = ""
    env["http_proxy"] = ""
    env["https_proxy"] = ""
    return env


def main():
    ap = argparse.ArgumentParser(description="coupon-push 队列驱动推送封装")
    ap.add_argument("--queue", default=DEFAULT_QUEUE, help="push-queue.json 路径")
    ap.add_argument("--root", default=None, help="本地根目录（默认由 queue 路径推导）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不推送不写回")
    ap.add_argument("--keyword", default=None, help="真页验真关键词（仅对 .html 生效）")
    ap.add_argument("--only", default=None, help="只处理指定 taskId")
    ap.add_argument("--no-wait-pages", action="store_true", help="跳过 Pages 重建等待（仅调试）")
    ap.add_argument("--strict", action="store_true", help="待确认>0 也硬阻断（恢复 SKILL 原文语义）")
    a = ap.parse_args()

    queue_path = a.queue
    root = a.root or os.path.dirname(os.path.dirname(queue_path))
    log_dir = os.path.dirname(queue_path)
    push_log_path = os.path.join(log_dir, "push-log.json")
    gh = gh_push_path()
    env = build_env()

    print(f"[init] queue={queue_path}")
    print(f"[init] root ={root}")
    print(f"[init] engine={gh}  ({'存在' if os.path.isfile(gh) else '缺失!!'})")
    if not os.path.isfile(gh):
        print("FATAL: gh_push.py 缺失，无法推送"); sys.exit(1)

    q = load_json(queue_path, {"version": 1, "entries": []})
    push_log = load_json(push_log_path, {"version": 1, "files": {}})
    entries = q.get("entries", [])

    pending = [e for e in entries if e.get("state") == "MERGED_READY"]
    if a.only:
        pending = [e for e in pending if e.get("taskId") == a.only]
    pending.sort(key=lambda e: e.get("mergedAt", ""))

    if not pending:
        print("[done] 无 MERGED_READY 待推送任务。")
        # 仍跑漂移检测安全网
        drift_check(root, push_log, set(), dry=a.dry_run)
        sys.exit(0)

    print(f"[plan] 待推送 {len(pending)} 条（FIFO）:")
    for e in pending:
        print(f"  - {e.get('taskId')}  {e.get('title','')[:30]}  files={e.get('files')}")

    pushed_this_run = set()
    stopped = False

    for e in pending:
        if stopped:
            break
        tid = e.get("taskId")
        files = e.get("files", [])
        print(f"\n=== 处理 {tid} ===")

        block, warn = precheck(root, files, strict=a.strict)
        for w in warn:
            print(f"[warn] 预检提示: {w}")
        if block:
            e["state"] = "NEEDS_CONFIRM"
            e["note"] = "预检阻断: " + "; ".join(block)
            print(f"[BLOCK] 预检未过，置 NEEDS_CONFIRM 并停止队列: {block}")
            stopped = True
            break

        # 收集本次待推（去重）
        puts = []
        for rel in files:
            if rel in pushed_this_run:
                continue
            remote = remote_for(push_log, rel)
            msg = f"chore: push {rel} via coupon-push ({tid})"
            puts.append((rel, remote, msg))
            pushed_this_run.add(rel)

        if not puts:
            print("[skip] 本 entry 文件本轮均已推过。")
            e["state"] = "PUSHED"
            e["pushedAt"] = now_iso()
            continue

        # 组装 gh_push.py 调用
        cmd = [sys.executable, gh, "--repo", REPO, "--root", root, "--branch", BRANCH]
        for rel, remote, msg in puts:
            cmd += ["--put", f"{rel}::{remote}::{msg}"]
        if not a.no_wait_pages:
            cmd += ["--wait-pages"]
        if a.keyword and any(r.endswith(".html") for _, r, _ in puts):
            cmd += ["--live-grep", a.keyword]
        if a.dry_run:
            cmd += ["--dry-run"]

        print(f"[push] 调用 gh_push.py 推 {len(puts)} 个文件" + (" (dry-run)" if a.dry_run else ""))
        rc = subprocess.run(cmd, env=env).returncode
        if rc != 0:
            e["state"] = "NEEDS_CONFIRM"
            e["note"] = f"gh_push.py 返回 {rc}，推送失败，停止队列"
            print(f"[BLOCK] 推送失败 rc={rc}，置 NEEDS_CONFIRM 并停止队列。")
            stopped = True
            break

        # 抓取远端 sha 回填（供漂移检测）
        sha_map = {}
        for rel, remote, _ in puts:
            sha_map[remote] = fetch_remote_sha(REPO, BRANCH, remote, env)
            # 同步 push-log.json
            push_log.setdefault("files", {}).setdefault(rel, {})
            push_log["files"][rel]["remotePath"] = remote
            push_log["files"][rel]["lastPushedSha"] = sha_map[remote]
            push_log["files"][rel]["lastPushedAt"] = now_iso()

        e["state"] = "PUSHED"
        e["pushedAt"] = now_iso()
        e["remoteSha"] = sha_map
        print(f"[ok] {tid} 已推送并标记 PUSHED。")

    # 写回状态
    if not a.dry_run:
        save_json(queue_path, q)
        save_json(push_log_path, push_log)
        print("\n[write] push-queue.json / push-log.json 已写回。")
    else:
        print("\n[dry-run] 未写回。")

    drift_check(root, push_log, pushed_this_run, dry=a.dry_run)
    sys.exit(0 if not stopped else 1)


def drift_check(root, push_log, pushed_this_run, dry=False):
    print("\n=== 漂移检测（安全网）===")
    flagged = []
    for rel, meta in push_log.get("files", {}).items():
        if rel in pushed_this_run:
            continue
        full = os.path.join(root, rel)
        local = git_blob_sha1(full)
        last = meta.get("lastPushedSha")
        if local and last and local != last:
            flagged.append((rel, local[:10], last[:10]))
    if flagged:
        print("⚠️ 发现未登记的本地改动（不自动推，请确认）：")
        for rel, lo, la in flagged:
            print(f"  - {rel}: local {lo} ≠ lastPushed {la}")
    else:
        print("✓ 已知文件本地与 lastPushedSha 一致，无漂移。")


if __name__ == "__main__":
    main()
