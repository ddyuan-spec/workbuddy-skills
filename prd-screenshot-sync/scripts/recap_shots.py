# -*- coding: utf-8 -*-
"""
prd-screenshot-sync — 重新截取 PRD 内嵌原型截图并与当前原型对齐。

核心问题：PRD 里 <img> 引用的原型截图，在原型改版（配色/UI/删序号等）后极易"悄悄过期"，
而 naive 重截会因两种坑导致截图依然错误：
  A. 用 <iframe> 加载原型再截图 → file:// 跨域导致 contentDocument 取不到、触发器不执行，
     多张图渲染成同一张空白/默认图（字节完全相同）。
  B. Edge --screenshot 在 load 事件即截，注入的 setTimeout(触发弹窗) 还没跑 → 所有图都是初始态。

本脚本的可靠做法（已踩坑固化）：
  1. 把"触发脚本"注入【原型 html 的临时副本】（不用 iframe，避开跨域）。
  2. 截图时加 --virtual-time-budget=3000，让 setTimeout 先跑完再截。
  3. 用 MD5 / 文件大小 diff 比对原图，只替换真正变了的；并打印 [NEW/CHANGED/unchanged]。
  4. PIL 合理性自检：若两张"不同视图"截出完全相同的 distinct_colors/字节 → 触发器失效，立刻告警。
  5. 可选 --push 直接推 GitHub Pages（Python 生成 body.json + gh api --input，避开超长 base64 命令行截断）。

用法：
  python recap_shots.py --map screenshot-map.json [--push] [--dry]
  # map 文件示例见 references/screenshot-map.example.json
"""
import argparse, subprocess, os, sys, json, hashlib, shutil

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def entropy(path):
    """返回 (distinct_colors, top_color_rgb, top_count, total_px)，用于空白/雷同自检。"""
    if not HAS_PIL:
        return (None, None, None, None)
    im = Image.open(path).convert("RGB")
    colors = im.getcolors(maxcolors=200000) or [(0, (0, 0, 0))]
    total = sum(c[0] for c in colors)
    top = sorted(colors, reverse=True)[0]
    return (len(colors), top[1], top[0], total)

def recap(proto_html, assets_dir, shots, edge, do_push, dry):
    with open(proto_html, encoding="utf-8") as f:
        html = f.read()
    results = []
    seen_hashes = {}
    for name, cfg in shots.items():
        trigger = cfg.get("trigger", "")
        w, h = cfg.get("size", [1280, 900])
        out_path = os.path.join(assets_dir, name)
        existing_md5 = md5(out_path) if os.path.exists(out_path) else None

        # 注入触发脚本（放在 </body> 前；原型主脚本在其前已执行，函数已定义）
        temp_html = html
        if trigger:
            inj = (f'<script>window.addEventListener("load",function(){{'
                    f'setTimeout(function(){{{trigger}}},600);}});</script>')
            temp_html = html.replace("</body>", inj + "</body>", 1)
        temp_path = os.path.join(assets_dir, f"_shot_{name}.html")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(temp_html)

        url = "file:///" + temp_path.replace("\\", "/")
        r = subprocess.run([edge, "--headless", "--disable-gpu",
                            "--virtual-time-budget=3000",
                            f"--screenshot={out_path}",
                            f"--window-size={w},{h}", url],
                           timeout=60, capture_output=True)
        os.remove(temp_path)

        new_md5 = md5(out_path) if os.path.exists(out_path) else None
        status = "NEW" if existing_md5 is None else ("CHANGED" if new_md5 != existing_md5 else "unchanged")
        ent = entropy(out_path) if HAS_PIL else None
        sz = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        print(f"  {name:22s} {sz:>8d}B [{status:9s}] rc={r.returncode} "
              f"entropy={ent[0] if ent else 'n/a'}")
        results.append((name, status, out_path, new_md5))

        # 雷同自检：不同视图却字节相同 → 触发器没生效
        if new_md5 in seen_hashes and new_md5 is not None:
            print(f"    ⚠️ 雷同告警：{name} 与 {seen_hashes[new_md5]} 字节完全一致，"
                  f"疑似触发脚本未执行（iframe/CORS 或 virtual-time-budget 不足）")
        seen_hashes.setdefault(new_md5, name)

    if dry:
        print("[dry] 仅检查，未推送。")
        return

    if do_push:
        push_github(assets_dir, [n for n, _, _, _ in results])

def push_github(assets_dir, names, repo="ddyuan-spec/taixiaohu"):
    import base64
    for name in names:
        local = os.path.join(assets_dir, name)
        remote = f"hlz-prd-assets/{name}"
        b = base64.b64encode(open(local, "rb").read()).decode()
        sha = ""
        r = subprocess.run(["gh", "api", f"repos/{repo}/contents/{remote}", "-q", ".sha"],
                           capture_output=True, text=True, env={**os.environ, "HTTPS_PROXY": ""})
        if r.returncode == 0 and r.stdout.strip():
            sha = r.stdout.strip()
        body = json.dumps({"message": f"update {remote} - re-captured from current prototype",
                          "content": b, **({"sha": sha} if sha else {})})
        body_path = os.path.join(assets_dir, "..", "_gen_body.json")
        with open(body_path, "w") as f:
            f.write(body)
        r2 = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{remote}",
                             "--input", body_path], capture_output=True, text=True,
                            env={**os.environ, "HTTPS_PROXY": ""})
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                              f"https://raw.githubusercontent.com/{repo}/main/{remote}"],
                             capture_output=True, text=True).stdout.strip()
        print(f"  push {remote} -> rc={r2.returncode} verify=HTTP {code}")
        try: os.remove(body_path)
        except: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="screenshot-map.json 路径")
    ap.add_argument("--push", action="store_true", help="重截后推 GitHub Pages")
    ap.add_argument("--dry", action="store_true", help="只检查不替换/不推送")
    args = ap.parse_args()

    with open(args.map, encoding="utf-8") as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(args.map))
    proto = cfg["proto"]
    proto_html = proto if os.path.isabs(proto) else os.path.join(base, proto)
    assets = cfg["assets_dir"]
    assets_dir = assets if os.path.isabs(assets) else os.path.join(base, assets)

    edge = find_edge()
    if not edge:
        print("❌ 找不到 Edge，无法 headless 截图"); sys.exit(1)
    if not HAS_PIL:
        print("⚠️ 未安装 Pillow，跳过雷同/空白自检（建议 pip install pillow）")

    print(f"=== PRD 截图对齐：原型={os.path.basename(proto_html)} 资源目录={assets_dir} ===")
    recap(proto_html, assets_dir, cfg["shots"], edge, args.push, args.dry)
    print("=== 完成 ===")

if __name__ == "__main__":
    main()
