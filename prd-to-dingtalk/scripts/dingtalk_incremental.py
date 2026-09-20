#!/usr/bin/env python3
"""
增量同步 PRD → 钉钉文档（模式 A：图片增量 + 文本全量）。

解决痛点：每轮全量 `media insert` 把全部图片重传一遍，费 OSS/时间，大文档必踩 verify 坑。
本脚本只做「纯 Python 分析」：抽取图片 → 算内容指纹 → 与 manifest 比对 → 判定
「复用(不传) / 变化需传 / 新增需传」，并产出改图后用于 overwrite 的零外链 MD 骨架。
实际 dws 调用（media upload / doc update）按 skill 红线由 Bash 执行（见 --apply 产出的
apply 脚本），本脚本不直接 subprocess 调 dws。

依赖：
- 复用同目录 prd_html_to_dingtalk_md.py 转 MD（需 bs4/markdownify/lxml）。
- 缩图复用同目录 resize_image.py（需 Pillow）。

用法：
  # 离线校验（不碰钉钉、不真实上传）：用本地资源目录算指纹，建立/比对基线
  python dingtalk_incremental.py <prd.html> --mode A --dry-run \
      --manifest _exp.json --local-assets-dir _prd_imgs_video_v01

  # 真实应用（生成 apply 脚本，由 Bash 跑 dws）：
  python dingtalk_incremental.py <prd.html> --node <nodeId> --mode A \
      --manifest _dingtalk_sync/<base>.json --apply

判定规则（key = 图片稳定标识，默认取 URL 去掉 query 后的相对路径；本地模式取文件名）：
- manifest 有同 key 且 指纹(etag 或 sha256) 未变 → REUSE（复用旧 resourceUrl，不传）
- manifest 有同 key 但 指纹变了            → CHANGED（需重传，拿新 URL）
- manifest 无此 key                       → NEW（需上传）
- 仅 --dry-run 时不写 resourceUrl，只记录指纹，供下一轮比对。
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LVYUNJI_BASE = "https://ddyuan-spec.github.io/lvyunji/"
RESIZE_SCRIPT = HERE / "resize_image.py"

# ---------- 复用转换脚本 ----------
sys.path.insert(0, str(HERE))
try:
    from prd_html_to_dingtalk_md import html_to_dingtalk_md  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"[warn] 无法 import 转换脚本: {exc}；将用内置兜底转换", file=sys.stderr)

    def html_to_dingtalk_md(html_path, output_path=None):
        raise RuntimeError("转换脚本不可用")


# ---------- 工具 ----------

def img_md_pattern():
    return re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def derive_key(url: str) -> str:
    """稳定标识：去掉 query/fragment，取 lvyunji 之后的相对路径；否则用完整 URL。"""
    u = url.split("?")[0].split("#")[0]
    if u.startswith(LVYUNJI_BASE):
        return u[len(LVYUNJI_BASE):].lstrip("/")
    return u


def local_path_for(url: str, local_dir: Path | None) -> Path | None:
    if not local_dir:
        return None
    fname = url.split("?")[0].split("#")[0].rstrip("/").split("/")[-1]
    p = local_dir / fname
    return p if p.exists() else None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def head_etag(url: str, timeout=15):
    """HEAD 请求拿 ETag；失败返回 None。"""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "dingtalk-incremental/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            etag = resp.headers.get("ETag")
            return etag.strip().strip('"') if etag else None
    except Exception:
        return None


def fetch_online(url: str, timeout=30):
    """返回 (bytes, etag)。etag 可能为 None。"""
    req = urllib.request.Request(url, headers={"User-Agent": "dingtalk-incremental/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        etag = resp.headers.get("ETag")
        if etag:
            etag = etag.strip().strip('"')
        return data, etag


def get_identity(url: str, local_dir: Path | None, offline: bool, stored_etag: str | None = None):
    """返回 (identity, bytes_or_None)。offline 且无本地文件时返回 (None, None)。

    - 本地目录优先：直接算 sha（无需下载）。
    - 在线：下载后按内容 sha256 判指纹。
    - ⚠️ 不用 HTTP ETag 做指纹：GitHub raw（Fastly/Apache 系）的 ETag 含 mtime/inode，
      每次 push 整树 mtime 变化 → 全部误判 CHANGED（2026-09-10 踩坑，18/18 CHANGED）。
      内容 sha256 才是跨 push 稳定的指纹。
    """
    lp = local_path_for(url, local_dir) if local_dir else None
    if lp:
        data = lp.read_bytes()
        return "sha256:" + sha256_bytes(data), data
    if offline:
        return None, None
    try:
        data, _etag = fetch_online(url)
        return "sha256:" + sha256_bytes(data), data
    except Exception as exc:
        print(f"[warn] 拉取失败 {url}: {exc}", file=sys.stderr)
        return None, None


# ---------- 主流程 ----------

def extract_images(md: str):
    out = []
    for m in img_md_pattern().finditer(md):
        alt, url = m.group(1), m.group(2)
        out.append({"key": derive_key(url), "alt": alt, "url": url})
    return out


def load_manifest(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"images": {}}


def save_manifest(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze(html_path: Path, manifest: dict, local_dir: Path | None, offline: bool, mode: str):
    """返回 (images_analysis, md_text)。"""
    md_text = html_to_dingtalk_md(str(html_path), None)
    imgs = extract_images(md_text)
    prev = manifest.get("images", {})
    results = []
    for im in imgs:
        key = im["key"]
        stored_etag = prev.get(key, {}).get("etag")
        identity, data = get_identity(im["url"], local_dir, offline, stored_etag)
        if identity is None:
            # 拿不到指纹：保守当作 NEW，需上传（真实应用会下载）
            status = "NEW"
            rec = {"key": key, "alt": im["alt"], "url": im["url"], "status": status,
                   "identity": None, "resourceUrl": prev.get(key, {}).get("resourceUrl"),
                   "data": data}
        elif key in prev and prev[key].get("identity") == identity:
            status = "REUSE"
            rec = {"key": key, "alt": im["alt"], "url": im["url"], "status": status,
                   "identity": identity, "resourceUrl": prev[key].get("resourceUrl"),
                   "data": None}
        elif key in prev:
            status = "CHANGED"
            rec = {"key": key, "alt": im["alt"], "url": im["url"], "status": status,
                   "identity": identity, "resourceUrl": None, "data": data}
        else:
            status = "NEW"
            rec = {"key": key, "alt": im["alt"], "url": im["url"], "status": status,
                   "identity": identity, "resourceUrl": None, "data": data}
        results.append(rec)
    return results, md_text


def build_zeroext_md(md_text: str, reused_map: dict):
    """把 REUSE 图替换为已存 resourceUrl；其余保持原 URL（待上传后由 apply 脚本替换）。"""
    def repl(m):
        alt, url = m.group(1), m.group(2)
        key = derive_key(url)
        if key in reused_map:
            return f"![{alt}]({reused_map[key]})"
        return m.group(0)
    return img_md_pattern().sub(repl, md_text)


def write_apply_script(node_id, to_upload, reused_map, md_zeroext_path, manifest_path, out_dir):
    """产出可由 Bash 执行的 apply 脚本（dws 调用在此，遵守 skill 红线）。"""
    out_abs = Path(out_dir).resolve()
    md_abs = Path(md_zeroext_path).resolve()
    man_abs = Path(manifest_path).resolve()
    script = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    script.append(f'NODE="{node_id}"')
    script.append(f'MANIFEST="{man_abs.as_posix()}"')
    script.append(f'MD_ZEROEXT="{md_abs.as_posix()}"')
    script.append(f'RESULTS="{out_abs.as_posix()}/_upload_results.json"')
    script.append('echo "[]" > "$RESULTS"')
    script.append("")
    script.append("# ---- 阶段1：上传变化/新增图，收集 key->resourceUrl ----")
    for im in to_upload:
        lp = local_path_for(im["url"], None) or im["_local"]
        lp = Path(lp).as_posix()
        key = im["key"]
        script.append(f'echo "upload: {key}"')
        script.append(
            f'RURL=$(dws doc media upload --node "$NODE" --file "{lp}" --yes --format json '
            f'| python -c "import sys,json;d=json.load(sys.stdin);'
            f'print(d.get(\'resourceUrl\') or d.get(\'data\',{{}}).get(\'resourceUrl\') '
            f'or d.get(\'error\',{{}}).get(\'details\',{{}}).get(\'resourceUrl\',\'\'))")'
        )
        script.append(
            f'python - "$RESULTS" "{key}" "$RURL" <<\'PY\''
        )
        script.append("import sys,json")
        script.append("p,k,r=sys.argv[1],sys.argv[2],sys.argv[3]")
        script.append("a=json.load(open(p,encoding='utf-8'))")
        script.append("a.append({'key':k,'resourceUrl':r})")
        script.append("json.dump(a,open(p,'w',encoding='utf-8'))")
        script.append("PY")
    script.append("")
    script.append("# ---- 阶段2：把上传结果填进 MD，再 overwrite ----")
    # 独立 _substitute.py（函数定义在文件里合法，避免内联 def 语法坑）
    sub_py = out_abs / "_substitute.py"
    sub_content = (
        "import json, re\n"
        f"RES = r'{out_abs.as_posix()}/_upload_results.json'\n"
        f"MD = r'{md_abs.as_posix()}'\n"
        "res = json.load(open(RES, encoding='utf-8'))\n"
        "m = {x['key']: x['resourceUrl'] for x in res}\n"
        "md = open(MD, encoding='utf-8').read()\n"
        "def f(mt):\n"
        "    a, u = mt.group(1), mt.group(2)\n"
        "    k = u.split('?')[0].split('#')[0]\n"
        "    if k.startswith('https://ddyuan-spec.github.io/lvyunji/'):\n"
        "        k = k[len('https://ddyuan-spec.github.io/lvyunji/'):].lstrip('/')\n"
        "    return ('![%s](%s)' % (a, m[k])) if k in m else mt.group(0)\n"
        "md = re.sub(r'!\\[([^\\]]*)\\]\\(([^)\\s]+)[^\\)]*\\)', f, md)\n"
        "open(MD + '.final', 'w', encoding='utf-8').write(md)\n"
        "print('substituted, github外链残留:', md.count('githubusercontent') + md.count('github.io'))\n"
        "print('final 图行数:', md.count('\\n!['))\n"
    )
    sub_py.write_text(sub_content, encoding="utf-8", newline="\n")
    script.append(f'python "{sub_py.as_posix()}"')
    script.append('dws doc update --node "$NODE" --content-file "$MD_ZEROEXT.final" --mode overwrite --yes --format json')
    script.append("")
    script.append("# ---- 阶段3：回读验证零外链 ----")
    script.append('dws doc read --node "$NODE" --format json --content-format jsonml --scope tags --tags img > _read.json')
    script.append('echo "github外链命中: $(grep -c githubusercontent _read.json) (应为0)"')
    script.append('echo "core/api/resources命中: $(grep -c core/api/resources _read.json) (应>0)"')
    out = out_dir / f"_dingtalk_apply_{node_id}.sh"
    out.write_text("\n".join(script), encoding="utf-8", newline="\n")
    return out


def main():
    ap = argparse.ArgumentParser(description="增量同步 PRD→钉钉（模式A）")
    ap.add_argument("html", help="PRD 的 HTML 文件（应取自 GitHub 已确认版）")
    ap.add_argument("--node", help="目标钉钉文档 nodeId（--apply 必填）")
    ap.add_argument("--mode", default="A", choices=["A", "B"], help="A=图片增量+文本全量(默认)")
    ap.add_argument("--manifest", required=True, help="manifest JSON 路径（图片 key↔指纹/resourceUrl）")
    ap.add_argument("--local-assets-dir", help="本地图片目录（离线校验用，跳过下载）")
    ap.add_argument("--offline", action="store_true", help="完全离线：无本地文件则指纹=None")
    ap.add_argument("--dry-run", action="store_true", help="只分析并报告，不产 apply 脚本、不写 resourceUrl")
    ap.add_argument("--apply", action="store_true", help="产出 apply 脚本（由 Bash 执行 dws）")
    ap.add_argument("--finalize", metavar="RESULTS_JSON",
                    help="apply 脚本跑完后，把 _upload_results.json 里的 resourceUrl 回填进 manifest（建/更新基线）")
    ap.add_argument("--out-dir", default=".", help="产出文件目录")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    # --finalize：跑完 apply 脚本后回填 resourceUrl，避免下一轮全量重传
    if args.finalize:
        manifest = load_manifest(manifest_path)
        res_path = Path(args.finalize)
        if not res_path.exists():
            print(f"[error] 结果文件不存在: {res_path}", file=sys.stderr); sys.exit(1)
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[error] 结果文件解析失败: {e}", file=sys.stderr); sys.exit(1)
        imgs = manifest.setdefault("images", {})
        n = 0
        for x in res:
            k, u = x.get("key"), x.get("resourceUrl")
            if not k or not u:
                continue
            imgs.setdefault(k, {"identity": ""})["resourceUrl"] = u
            n += 1
        save_manifest(manifest_path, manifest)
        print(f"[finalize] 已回填 {n} 张图的 resourceUrl → {manifest_path}")
        print(f"[finalize] manifest 图片总数 {len(imgs)}；其中已有 resourceUrl: "
              f"{sum(1 for v in imgs.values() if v.get('resourceUrl'))}")
        return 0

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"HTML 不存在: {html_path}", file=sys.stderr); sys.exit(1)
    manifest_path = Path(args.manifest)
    local_dir = Path(args.local_assets_dir) if args.local_assets_dir else None
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)
    results, md_text = analyze(html_path, manifest, local_dir, args.offline, args.mode)

    n_reuse = sum(1 for r in results if r["status"] == "REUSE")
    n_changed = sum(1 for r in results if r["status"] == "CHANGED")
    n_new = sum(1 for r in results if r["status"] == "NEW")
    n_total = len(results)

    print(f"\n=== 图片增量分析（模式 {args.mode}）===")
    print(f"图片总数: {n_total}")
    print(f"  REUSE(复用旧URL,不传): {n_reuse}")
    print(f"  CHANGED(需重传):       {n_changed}")
    print(f"  NEW(需上传):           {n_new}")
    print(f"  本轮将上传: {n_changed + n_new} / {n_total} "
          f"({0 if n_total==0 else round((n_changed+n_new)/n_total*100)}%)")
    for r in results:
        if r["status"] != "REUSE":
            print(f"   [{r['status']:>6}] {r['key']}")

    # 更新 manifest 指纹（dry-run 也写，便于下一轮比对；resourceUrl 仅 apply 且有值时写）
    new_images = {}
    for r in results:
        entry = {"identity": r["identity"]}
        if r["identity"] and r["identity"].startswith("etag:"):
            entry["etag"] = r["identity"][len("etag:"):]
        if r["resourceUrl"]:
            entry["resourceUrl"] = r["resourceUrl"]
        new_images[r["key"]] = entry
    manifest["images"] = new_images

    if args.dry_run:
        save_manifest(manifest_path, manifest)
        print(f"\n[dry-run] 已写基线指纹 manifest: {manifest_path}（未上传、未写 resourceUrl）")
        return 0

    if not args.apply:
        # 既不 dry-run 也不 apply：只报告
        save_manifest(manifest_path, manifest)
        print("\n[info] 非 dry-run 且未指定 --apply：仅报告。加 --apply 生成 apply 脚本。")
        return 0

    if not args.node:
        print("[error] --apply 需要 --node <nodeId>", file=sys.stderr); sys.exit(1)

    reused_map = {r["key"]: r["resourceUrl"] for r in results if r["status"] == "REUSE" and r["resourceUrl"]}
    md_zeroext = build_zeroext_md(md_text, reused_map)
    md_zeroext_path = out_dir / (html_path.stem + ".zeroext.md")
    md_zeroext_path.write_text(md_zeroext, encoding="utf-8", newline="\n")

    to_upload = []
    for r in results:
        if r["status"] in ("CHANGED", "NEW"):
            # 准备本地待传文件：优先用已下载 bytes；否则标记需下载
            if r["data"] is not None:
                tmp = out_dir / ("_up_" + r["key"].replace("/", "_"))
                tmp.write_bytes(r["data"])
                # 缩图
                if RESIZE_SCRIPT.exists():
                    try:
                        subprocess.run([sys.executable, str(RESIZE_SCRIPT), str(tmp), str(tmp)],
                                       check=False, capture_output=True)
                    except Exception:
                        pass
                r["_local"] = str(tmp)
            else:
                r["_local"] = r["url"]  # 真实应用由 apply 脚本下载（此处离线缺数据）
            to_upload.append(r)

    # 先把「指纹基线」落盘（resourceUrl 待上传后 --finalize 回填），
    # 否则 apply 中断/忘记回填会导致下一轮全量重传
    save_manifest(manifest_path, manifest)
    apply_script = write_apply_script(args.node, to_upload, reused_map, md_zeroext_path, manifest_path, out_dir)
    print(f"[apply] 已写指纹基线 manifest（resourceUrl 待回填）: {manifest_path}")
    print(f"\n[apply] 零外链 MD: {md_zeroext_path}")
    print(f"[apply] 待上传图: {len(to_upload)} 张")
    print(f"[apply] apply 脚本（用 Bash 执行 dws）: {apply_script}")
    print(f"[apply] 运行: bash \"{apply_script}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
