#!/usr/bin/env python3
"""
prd-sync —— 管理 PRD 在「本地草稿 / GitHub Pages(已确认) / 钉钉文档」三端的版本同步。

设计原则（GitHub 为主文档）：
  - 本地 HTML 只是「草稿」，可能领先于已确认版本（用户在改、未推送）。
  - GitHub Pages 是「已确认最终版」：只有用户确认后，本地草稿才被推送上来。
  - 钉钉文档是「从 GitHub 派生的镜像」：永远以 GitHub 已确认版本为基准同步，
    绝不直接从本地草稿推钉钉（避免把未确认内容发出去）。

版本号来源优先级（各端各自提取）：
  1. HTML 里的 <meta name="prd-version" content="V0.4">
  2. 兜底：变更记录表（<tr><td>Vx.y</td>...）最后一行

manifest 文件：<cwd>/prd-publish-manifest.json
子命令：
  register   注册/更新一个 PRD 的三端信息
  version    打印从本地 HTML 提取的草稿版本号（调试用）
  status     对比三端版本，输出同步状态表
             —— 权威一致性 = GitHub(已确认) == 钉钉(已同步)
             —— 本地草稿领先 GitHub 是「未确认」提示，不算漂移
  record     某端发布后，记录该端版本号与同步时间
             —— record --target github   : 把本地草稿「确认推送」到 GitHub
             —— record --target dingtalk : 钉钉从 GitHub 已确认版派生，
                                           若本地草稿仍领先 GitHub 则拒绝（需先确认）
  bump       升级草稿版本号（同时改本地 HTML meta + manifest 本地版本）
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

MANIFEST = "prd-publish-manifest.json"

VERSION_RE = re.compile(r"V(\d+\.\d+(?:\.\d+)?)")
META_RE = re.compile(
    r'<meta\s+name=["\']prd-version["\']\s+content=["\'](V[\d.]+)["\']', re.I
)
CHANGELOG_RE = re.compile(r"<tr>\s*<td>(V[\d.]+)</td>", re.I)


def now_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def extract_version(html_text: str):
    m = META_RE.search(html_text)
    if m:
        return m.group(1)
    rows = CHANGELOG_RE.findall(html_text)
    if rows:
        return rows[-1]
    return None


def load_manifest(cwd: Path) -> dict:
    p = cwd / MANIFEST
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"prds": []}
    return {"prds": []}


def save_manifest(manifest: dict, cwd: Path) -> Path:
    p = cwd / MANIFEST
    p.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return p


def find_prd(manifest: dict, file: str = None, name: str = None):
    for prd in manifest["prds"]:
        if file and prd.get("file") == file:
            return prd
        if name and prd.get("name") == name:
            return prd
    return None


def read_local_version(cwd: Path, prd: dict):
    f = cwd / prd["file"] if prd.get("file") else None
    if f and f.exists():
        return extract_version(f.read_text(encoding="utf-8", errors="ignore"))
    return prd.get("local_version", "<missing>")


def fetch_github_version(raw_url: str):
    if not raw_url:
        return "<n/a>"
    try:
        req = urllib.request.Request(
            raw_url, headers={"User-Agent": "prd-sync"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode("utf-8", "ignore")
        return extract_version(text) or "<no-version-in-page>"
    except Exception as e:  # noqa: BLE001
        return f"<fetch-failed:{type(e).__name__}>"


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------
def cmd_register(args):
    cwd = Path(args.cwd)
    manifest = load_manifest(cwd)
    prd = find_prd(manifest, file=args.file, name=args.name)
    if prd is None:
        prd = {"name": args.name or args.file, "file": args.file}
        manifest["prds"].append(prd)

    prd["name"] = args.name or prd.get("name")
    prd["file"] = args.file or prd.get("file")

    local_version = read_local_version(cwd, prd) or args.version or "<unknown>"

    if args.github_url or args.github_raw:
        prd.setdefault("github", {})
        if args.github_url:
            prd["github"]["url"] = args.github_url
        if args.github_raw:
            prd["github"]["raw_url"] = args.github_raw
        if args.github_version:
            prd["github"]["version"] = args.github_version
        elif args.github_synced:
            prd["github"]["version"] = local_version
            prd["github"]["synced_at"] = now_iso()

    if args.dingtalk_node or args.dingtalk_url:
        prd.setdefault("dingtalk", {})
        if args.dingtalk_node:
            prd["dingtalk"]["node_id"] = args.dingtalk_node
        if args.dingtalk_url:
            prd["dingtalk"]["url"] = args.dingtalk_url
        if args.dingtalk_version:
            prd["dingtalk"]["version"] = args.dingtalk_version
        elif args.dingtalk_synced:
            prd["dingtalk"]["version"] = local_version
            prd["dingtalk"]["synced_at"] = now_iso()

    prd["local_version"] = local_version
    p = save_manifest(manifest, cwd)
    print(f"Registered '{prd['name']}' (本地草稿 {local_version}) -> {p}")


def cmd_version(args):
    cwd = Path(args.cwd)
    text = (cwd / args.file).read_text(encoding="utf-8", errors="ignore")
    print(extract_version(text) or "<no-version-found>")


def cmd_status(args):
    cwd = Path(args.cwd)
    manifest = load_manifest(cwd)
    if not manifest["prds"]:
        print("manifest 为空，先用 register 注册 PRD。")
        return 1

    print(
        f"{'PRD':<24} {'草稿(本地)':<11} {'已确认(GitHub)':<20} {'已同步(钉钉)':<11} 状态"
    )
    print("-" * 100)
    any_diverged = False
    for prd in manifest["prds"]:
        if args.file and prd.get("file") != args.file:
            continue
        local = read_local_version(cwd, prd)
        gh = prd.get("github", {})
        gh_ver = fetch_github_version(gh.get("raw_url", ""))
        dt = prd.get("dingtalk", {})
        dt_ver = dt.get("version", "<n/a>")

        # 权威一致性：GitHub(已确认) == 钉钉(已同步)
        notes = []
        if gh_ver in ("<n/a>",) or dt_ver in ("<n/a>",):
            notes.append("钉钉/GitHub 记录缺失")
            any_diverged = True
        elif gh_ver != dt_ver:
            notes.append("钉钉落后于确认版(需同步)")
            any_diverged = True
        else:
            notes.append("✅ 钉钉已追平确认版")

        # 本地草稿领先 = 未确认提示（不算漂移，但提示用户去确认）
        if local not in ("<missing>",) and gh_ver not in (
            "<n/a>",
            "<fetch-failed:*>",
        ) and local != gh_ver:
            notes.append(f"⚠️ 本地草稿领先({local})未确认")

        state = " / ".join(notes)
        print(
            f"{prd.get('name','?'):<22} {str(local):<11} {str(gh_ver):<20} {str(dt_ver):<11} {state}"
        )
    print("-" * 100)
    print(
        "说明：GitHub 实时抓取 raw 校验(已确认版)；钉钉为最近一次派发记录。"
        "一致性以 GitHub==钉钉 为准；本地领先仅提示「未确认」，不视为漂移。"
    )
    return 1 if any_diverged else 0


def cmd_record(args):
    cwd = Path(args.cwd)
    manifest = load_manifest(cwd)
    prd = find_prd(manifest, file=args.file, name=args.name)
    if prd is None:
        print("未找到该 PRD，请先 register。", file=sys.stderr)
        return 1
    local = read_local_version(cwd, prd)

    if args.target == "github":
        # 确认推送：本地草稿 -> GitHub 已确认版
        prd.setdefault("github", {})
        if args.url:
            prd["github"]["url"] = args.url
        if args.raw:
            prd["github"]["raw_url"] = args.raw
        prd["github"]["version"] = local
        prd["github"]["synced_at"] = now_iso()
        print(f"GitHub 已确认 -> {local} @ {prd['github']['synced_at']}")
    else:
        # 钉钉从 GitHub 已确认版派生：必须 GitHub 可达且已确认
        gh = prd.setdefault("github", {})
        gh_ver = fetch_github_version(gh.get("raw_url", ""))
        if gh_ver in ("<n/a>",) or gh_ver.startswith("<fetch-failed"):
            print(
                "⛔ 无法获取 GitHub 已确认版本（raw 不可达），钉钉不能派生。请先确认 GitHub 可访问。",
                file=sys.stderr,
            )
            return 1
        # 守卫：本地草稿不能领先于已确认版（否则等于把未确认内容发出去）
        if local not in ("<missing>",) and local != gh_ver:
            print(
                f"⛔ 本地草稿({local})仍领先已确认版(GitHub {gh_ver})，"
                "请先把本地草稿确认推送到 GitHub，再同步钉钉。",
                file=sys.stderr,
            )
            return 1
        prd.setdefault("dingtalk", {})
        if args.node:
            prd["dingtalk"]["node_id"] = args.node
        if args.url:
            prd["dingtalk"]["url"] = args.url
        prd["dingtalk"]["version"] = gh_ver  # 派生自 GitHub 已确认版
        prd["dingtalk"]["synced_at"] = now_iso()
        print(
            f"钉钉已派生自 GitHub 确认版 -> {gh_ver} @ {prd['dingtalk']['synced_at']}"
        )
    prd["local_version"] = local
    save_manifest(manifest, cwd)
    return 0


def cmd_bump(args):
    cwd = Path(args.cwd)
    manifest = load_manifest(cwd)
    prd = find_prd(manifest, file=args.file, name=args.name)
    if prd is None:
        print("未找到该 PRD，请先 register。", file=sys.stderr)
        return 1
    new_ver = args.version
    f = cwd / prd["file"] if prd.get("file") else None
    if f and f.exists():
        text = f.read_text(encoding="utf-8")
        if META_RE.search(text):
            text = META_RE.sub(
                f'<meta name="prd-version" content="{new_ver}"', text
            )
        else:
            text = text.replace(
                "</title>",
                f'</title>\n<meta name="prd-version" content="{new_ver}">',
                1,
            )
        f.write_text(text, encoding="utf-8")
        print(f"已更新草稿 {f.name} 的版本 meta -> {new_ver}（仅本地，未确认）")
    prd["local_version"] = new_ver
    save_manifest(manifest, cwd)
    print(
        f"manifest 本地草稿版本 -> {new_ver}。"
        "下一步：确认无误后推 GitHub(record --target github) → 再同步钉钉(record --target dingtalk)。"
    )
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="PRD 三端版本同步管理（GitHub 为主文档）")
    p.add_argument("--cwd", default=".", help="项目目录（manifest 所在目录）")
    sub = p.add_subparsers(dest="cmd", required=True)

    reg = sub.add_parser("register", help="注册/更新 PRD 三端信息")
    reg.add_argument("--name")
    reg.add_argument("--file")
    reg.add_argument("--version")
    reg.add_argument("--github-url")
    reg.add_argument("--github-raw")
    reg.add_argument("--github-version")
    reg.add_argument("--github-synced", action="store_true")
    reg.add_argument("--dingtalk-node")
    reg.add_argument("--dingtalk-url")
    reg.add_argument("--dingtalk-version")
    reg.add_argument("--dingtalk-synced", action="store_true")
    reg.set_defaults(func=cmd_register)

    ver = sub.add_parser("version", help="打印本地 HTML 草稿版本号")
    ver.add_argument("file")
    ver.set_defaults(func=cmd_version)

    st = sub.add_parser("status", help="对比三端版本（GitHub 为主文档）")
    st.add_argument("--file", default=None)
    st.set_defaults(func=cmd_status)

    rc = sub.add_parser("record", help="记录某端发布")
    rc.add_argument("--target", choices=["github", "dingtalk"], required=True)
    rc.add_argument("--file")
    rc.add_argument("--name")
    rc.add_argument("--node")
    rc.add_argument("--url")
    rc.add_argument("--raw")
    rc.set_defaults(func=cmd_record)

    bm = sub.add_parser("bump", help="升级草稿版本号（仅本地，未确认）")
    bm.add_argument("--version", required=True)
    bm.add_argument("--file")
    bm.add_argument("--name")
    bm.set_defaults(func=cmd_bump)

    return p


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
