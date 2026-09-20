#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_to_draft.py —— 公众号「创建草稿」参考实现（原生微信 API）

调用链路：
  1) cgi-bin/token              拿 access_token（AppID + AppSecret）
  2) cgi-bin/material/add_material?type=image   上传封面图 → thumb_media_id
  3) cgi-bin/draft/add          创建草稿，content 必须是「微信兼容 HTML」
                                 （用 wechat_format.py 产出）

使用前提（来自对标文章《实测WorkBuddy打通公众号》）：
  * 在「微信开发者平台 → 我的业务 → 公众号 → 开发密钥」拿 AppID / AppSecret
    （2025-12-01 起旧「开发接口管理」路径已失效）
  * 把本机/服务端出口 IP 加进「API IP 白名单」
    （若用 WorkBuddy 原生公众号连接，则填 WorkBuddy 给你的 IP，无需本脚本）

依赖：仅标准库。封面图可选；不传 --thumb 会跳过 thumb_media_id（草稿仍可建，但无封面）。

用法：
  python push_to_draft.py \
      --appid <APPID> --secret <APPSECRET> \
      --title "标题" --author "作者" --digest "摘要" \
      --content wechat_content.html \
      --thumb cover.jpg
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={}&type=image"
ADD_DRAFT_URL = "https://api.weixin.qq.com/cgi-bin/draft/add?access_token={}"


def http_json(url, data=None, files=None, method="GET"):
    headers = {"User-Agent": "wechat-draft-push/1.0"}
    body = None
    if files:
        boundary = "----wxboundary7Q8x"
        parts = []
        for fld, path in files.items():
            fn = os.path.basename(path)
            with open(path, "rb") as f:
                c = f.read()
            parts.append(
                ("--" + boundary + "\r\n").encode()
                + (f'Content-Disposition: form-data; name="{fld}"; filename="{fn}"\r\n').encode()
                + b"Content-Type: application/octet-stream\r\n\r\n"
                + c + b"\r\n"
            )
        body = b"".join(parts) + ("--" + boundary + "--\r\n").encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = data.encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"errcode": e.code, "errmsg": e.read().decode("utf-8", "ignore")}
    except Exception as e:  # noqa
        return {"errcode": -1, "errmsg": str(e)}


def get_token(appid, secret):
    url = f"{TOKEN_URL}?grant_type=client_credential&appid={urllib.parse.quote(appid)}&secret={urllib.parse.quote(secret)}"
    r = http_json(url)
    return r.get("access_token")


def upload_thumb(token, image_path):
    url = ADD_MATERIAL_URL.format(token)
    r = http_json(url, files={"media": image_path})
    return r.get("media_id")


def add_draft(token, article):
    url = ADD_DRAFT_URL.format(token)
    payload = {"articles": [article]}
    r = http_json(url, data=json.dumps(payload, ensure_ascii=False))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appid", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--digest", default="")
    ap.add_argument("--content", required=True, help="微信兼容 HTML 文件（wechat_format.py 产出）")
    ap.add_argument("--thumb", default="", help="封面图本地路径（可选）")
    args = ap.parse_args()

    print("→ 获取 access_token ...")
    token = get_token(args.appid, args.secret)
    if not token:
        print("❌ 获取 access_token 失败，检查 AppID/AppSecret/IP 白名单")
        sys.exit(1)
    print("✅ token OK")

    thumb_media_id = ""
    if args.thumb:
        if not os.path.exists(args.thumb):
            print(f"⚠️ 封面图不存在：{args.thumb}，跳过 thumb_media_id")
        else:
            print("→ 上传封面图 ...")
            thumb_media_id = upload_thumb(token, args.thumb) or ""
            if thumb_media_id:
                print("✅ thumb_media_id:", thumb_media_id)
            else:
                print("⚠️ 封面上传失败，草稿将无封面")

    content = open(args.content, encoding="utf-8").read()
    article = {
        "title": args.title,
        "author": args.author,
        "digest": args.digest,
        "content": content,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    print("→ 创建草稿 ...")
    r = add_draft(token, article)
    if r.get("media_id") or r.get("errcode") == 0:
        print("✅ 草稿已创建！media_id =", r.get("media_id"))
        print("   打开公众号后台草稿箱即可见，人工审核后发布。")
    else:
        print("❌ 创建失败：", json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
