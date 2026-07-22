#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产出校验 Hook（requirement-workflow skill 附带）

用法:
  python produce-check-hook.py <需求文件夹> [--step N] [--expect 文件1 文件2 ...]
  python produce-check-hook.py <需求文件夹> --scope <功能生命周期标注.html>   # 范围确认门禁

功能（对应 skill「产出校验 Hook」通用三查）:
  1. 数量: 对照 --expect 清单，检查期望文件是否齐全（缺失告警）
  2. 格式: HTML 可解析无 0 字节；DOCX 合法 OOXML(zip 可打开)
  3. 内容错乱:
     - 乱码: 扫描 U+FFFD 替换符
     - 裂图/缺图: <img> src 为空/占位/本地文件不存在（外链仅提示，需联网另查）
     - 结构损坏: 主要块级标签开闭配对异常、疑似占位符文本
     - Markdown 残留: 检测 ```mermaid / ``` 流程图 等语法残留

输出: 每文件 ✅/❌ 报告 + 末尾结论；存在异常退出码 1，全过退出码 0。

范围确认门禁（--scope）:
  进入 Step 2 前调用，检查范围对齐草稿(功能生命周期标注.html)存在且含用户确认标记：
  - 确认标记 = 草稿内写入 SCOPE_CONFIRMED，或同目录存在 <stem>-范围已确认.md 伴随文件。
  - 缺失 → 门禁不通过（AI 须先让用户标注并显式确认范围）。
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

REPLACEMENT_CHAR = "\ufffd"
BLOCK_TAGS = ["div", "table", "tr", "td", "section", "article", "ul", "ol", "li"]
PLACEHOLDER_RE = re.compile(r"(待补充|待完善|todo|tbd|占位符)", re.I)
MD_FENCE_RE = re.compile(r"```(?:mermaid|markdown|flow|flowchart|sequence)", re.I)
IMG_RE = re.compile(r"<img[^>]*src=[\"']([^\"']*)[\"']", re.I)


def check_html(path: Path):
    issues = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"无法读取: {e}"]

    if not text.strip():
        issues.append("文件为空 (0 字节/无内容)")
        return issues

    # ① 乱码
    n = text.count(REPLACEMENT_CHAR)
    if n:
        issues.append(f"含 U+FFFD 乱码 {n} 处")

    # ④ Markdown 残留
    md = MD_FENCE_RE.findall(text)
    if md:
        issues.append(f"检测到 Markdown 代码块残留(疑似流程图): {sorted(set(md))}")

    # ② 裂图 / 缺图
    for m in IMG_RE.finditer(text):
        src = m.group(1).strip()
        if not src:
            issues.append("img 存在空 src")
        elif src.startswith("data:image"):
            continue
        elif src.startswith(("http://", "https://")):
            issues.append(f"img 外链(远端可能裂，需另查 404): {src[:64]}")
        else:
            p = (path.parent / src)
            if not p.exists():
                issues.append(f"img 本地文件不存在: {src}")

    # ③ 结构损坏（块级标签配对）
    opens = sum(len(re.findall(rf"<{t}\b", text, re.I)) for t in BLOCK_TAGS)
    closes = sum(len(re.findall(rf"</{t}>", text, re.I)) for t in BLOCK_TAGS)
    if opens - closes > 3:
        issues.append(f"块级标签疑似未配对(开 {opens} / 闭 {closes})")

    # 疑似占位符（仅在可见正文检测，排除 <style>/<script> 块与标签属性）
    no_block = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    no_block = re.sub(r"<script[^>]*>.*?</script>", " ", no_block, flags=re.I | re.S)
    text_only = re.sub(r"<[^>]+>", " ", no_block)
    if PLACEHOLDER_RE.search(text_only):
        issues.append("检测到疑似占位符文本(待补充/todo/占位)")

    return issues


def check_scope(path: Path):
    """范围确认门禁：检查范围对齐草稿存在且已获用户确认标记。"""
    issues = []
    if not path.exists():
        issues.append(f"范围对齐草稿缺失: {path}（Step1 须先产出功能生命周期标注.html）")
        return issues
    # 确认标记：AI 在用户标注确认后，应在该文件写入 SCOPE_CONFIRMED 标记，
    # 或在同目录生成 <stem>-范围已确认.md 伴随文件。
    txt = path.read_text(encoding="utf-8", errors="replace")
    confirmed_marker = "SCOPE_CONFIRMED" in txt
    companion = path.parent / (path.stem + "-范围已确认.md")
    if not (confirmed_marker or companion.exists()):
        issues.append("未检测到范围确认标记（缺 SCOPE_CONFIRMED 或 <stem>-范围已确认.md）；"
                      "须用户标注并显式确认范围后才可进 Step 2")
    return issues


def check_docx(path: Path):
    issues = []
    try:
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        if bad:
            issues.append(f"OOXML 损坏: {bad}")
        media = [n for n in z.namelist() if n.startswith("word/media/")]
        doc = z.read("word/document.xml").decode("utf-8", errors="replace")
        n = doc.count(REPLACEMENT_CHAR)
        if n:
            issues.append(f"document.xml 含 U+FFFD 乱码 {n} 处")
        if not media:
            issues.append("docx 内未内嵌任何图片(疑似图缺失/裂图风险)")
    except Exception as e:
        issues.append(f"无法打开 docx(非合法 OOXML?): {e}")
    return issues


def main():
    ap = argparse.ArgumentParser(description="requirement-workflow 产出校验 Hook")
    ap.add_argument("folder", help="需求交付文件夹路径")
    ap.add_argument("--step", default="?", help="当前步骤号(仅用于报告标注)")
    ap.add_argument("--expect", nargs="*", default=[], help="期望产出的文件名清单")
    ap.add_argument("--scope", default=None, help="范围确认门禁：传入功能生命周期标注.html 路径，"
                                                  "检查范围草稿存在且含用户确认标记")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"[错误] 目录不存在: {folder}")
        sys.exit(1)

    files = sorted([f for ext in ("*.html", "*.docx") for f in folder.rglob(ext)])
    print(f"=== 产出校验 Hook | step {args.step} | 目录 {folder} ===")

    ok = True

    # 范围确认门禁（可选，进入 Step 2 前调用）
    if args.scope:
        sp = Path(args.scope)
        iss = check_scope(sp)
        if iss:
            ok = False
            print(f"[范围门禁] ❌ {sp.name}:")
            for i in iss:
                print(f"    - {i}")
        else:
            print(f"[范围门禁] ✅ 范围已确认（{sp.name} 含确认标记 / 伴随确认文件）")

    # 数量
    if args.expect:
        have = {f.name for f in files}
        miss = [e for e in args.expect if e not in have]
        if miss:
            ok = False
            print(f"[数量] ❌ 缺失期望文件: {miss}")
        else:
            print(f"[数量] ✅ 期望文件齐全 ({len(args.expect)})")
    else:
        print(f"[数量] ℹ️  未指定 --expect，跳过数量比对（共 {len(files)} 个交付文件）")

    # 格式 + 内容错乱
    for f in files:
        if f.suffix == ".html":
            iss = check_html(f)
        elif f.suffix == ".docx":
            iss = check_docx(f)
        else:
            continue
        if iss:
            ok = False
            print(f"[内容] ❌ {f.name}:")
            for i in iss:
                print(f"    - {i}")
        else:
            print(f"[内容] ✅ {f.name} 无明显错乱(格式/乱码/裂图/结构)")

    print("===")
    if ok:
        print("结论: 全部通过 ✅ （仍建议 Step7/8 推送后查远端 404 + 预览页）")
        sys.exit(0)
    else:
        print("结论: 存在异常 ❌ ，需修复后重新运行本脚本")
        sys.exit(1)


if __name__ == "__main__":
    main()
