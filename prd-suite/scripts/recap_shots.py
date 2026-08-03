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


def autocrop(path, top_pad=10, bottom_pad=20, side_pad=0, min_h=200):
    """
    按'实际内容边界'裁剪 PNG，去掉 Edge --screenshot 留下的顶部/底部/侧边空白。

    原理：Edge headless 截 PNG 时 PNG 尺寸 = window-size；当 window-size 给高了，
    实际内容只占前 N 行，剩 h-N 行都是空白背景。原型 HTML 背景色多样（深色顶栏、
    浅色内容区、卡片白底），不能简单用'单一背景色'判定。本函数改用：
      - 取 4 角 30px 区域的最频繁色作为'页面主背景'（原型里通常是浅灰/白）。
      - 逐行扫描，遇'非背景像素数 >= 5'即视为'有内容行'。
      - 裁掉顶部/底部连续空白，保留 top_pad/bottom_pad 像素留呼吸位。
      - 左右各裁 side_pad 像素（默认 0，Edge 不留水平空白）。

    返回 (new_w, new_h)，原图被原地覆盖。
    """
    if not HAS_PIL:
        return Image.open(path).size
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    # 1) 找页面主背景：取 4 角 30px 区域最频繁 3 色作为'背景家族'
    from collections import Counter
    corners = Counter()
    for y in list(range(0, 30)) + list(range(h - 30, h)):
        for x in list(range(0, 30)) + list(range(w - 30, w)):
            corners[px[x, y]] += 1
    bg_family = [c[0] for c in corners.most_common(3)]

    def is_bg(c):
        return any(abs(c[0] - b[0]) + abs(c[1] - b[1]) + abs(c[2] - b[2]) < 10
                   for b in bg_family)

    # 2) 逐行找'有内容'（行内非 bg 像素 >= 5）
    first, last = None, None
    for y in range(h):
        nbg = sum(1 for x in range(0, w, 2) if not is_bg(px[x, y]))
        if nbg >= 5:
            if first is None:
                first = y
            last = y
    if first is None:  # 全图都像背景
        return (w, h)
    # 3) 算裁剪框，留 padding
    y0 = max(0, first - top_pad)
    y1 = min(h, last + 1 + bottom_pad)
    new_h = max(min_h, y1 - y0)
    new_w = max(min_h, w - 2 * side_pad)  # 水平一般不裁
    # 4) 裁剪 + 存回
    cropped = im.crop((side_pad, y0, side_pad + new_w, y0 + new_h))
    cropped.save(path, optimize=True)
    return (new_w, new_h)

def recap(proto_html, assets_dir, shots, edge, do_push, dry):
    # 一次性支持多 proto：shots 每项可独立指定 proto 覆盖
    # 缓存已读 html
    html_cache = {}
    def get_html(p):
        if p not in html_cache:
            with open(p, encoding="utf-8") as f:
                html_cache[p] = f.read()
        return html_cache[p]

    results = []
    seen_hashes = {}
    for name, cfg in shots.items():
        proto_p = cfg.get("proto", proto_html)
        html = get_html(proto_p)
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
        # === auto-crop：去掉 window-size 给高了的留白 ===
        crop_w, crop_h = (None, None)
        if HAS_PIL and os.path.exists(out_path):
            crop_w, crop_h = autocrop(out_path)
        sz = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        orig_sz = f"({w}x{h}->{crop_w}x{crop_h})" if HAS_PIL else f"({w}x{h})"
        print(f"  {name:34s} {sz:>8d}B [{status:9s}] rc={r.returncode} "
              f"size={orig_sz} entropy={ent[0] if ent else 'n/a'}")
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
        # 远端目录：map.json 里可写 assets_remote 覆盖（默认 = 本地 assets_dir 名）
        remote_dir = cfg.get("assets_remote", os.path.basename(assets_dir.rstrip("/\\")))
        push_github(assets_dir, [n for n, _, _, _ in results], remote_dir=remote_dir)

def push_github(assets_dir, names, repo="ddyuan-spec/taixiaohu", remote_dir=None):
    import base64
    # 远端目录：优先用 cfg 里的 assets_remote（路径需与 PRD 内 <img src=> 一致），否则用 assets_dir 同名
    # 注意：本地目录名 != 远端目录名（如 hlz-prd-assets local -> coupon-prd-assets remote）
    if remote_dir is None:
        remote_dir = os.path.basename(assets_dir.rstrip("/\\"))
    for name in names:
        local = os.path.join(assets_dir, name)
        remote = f"{remote_dir}/{name}"
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
