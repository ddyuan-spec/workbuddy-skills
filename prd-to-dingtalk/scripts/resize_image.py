#!/usr/bin/env python3
"""
Resize a local image to a smaller size before inserting into DingTalk.

默认缩放到原图的 1/3（即等比小 2/3），避免插入钉钉文档后图片过大、需手动调整。
保持原图宽高比（等比缩放）。

依赖：Pillow（managed Python 已预装：
  C:/Users/13364/.workbuddy/binaries/python/versions/3.13.12/python.exe）
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Missing dependency: Pillow. Install with: pip install Pillow")
    sys.exit(1)


SUFFIX_TO_FORMAT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".gif": "GIF",
    ".bmp": "BMP",
    ".webp": "WEBP",
}


def resize_image(
    input_path: str,
    output_path: str | None = None,
    factor: float = 1.0 / 3.0,
    max_dim: int | None = None,
) -> str:
    """
    等比缩放图片。

    :param input_path: 源图片路径
    :param output_path: 输出路径；为空时默认在文件名插入 _sm（如 foo.png -> foo_sm.png）
    :param factor: 缩放系数，默认 1/3（即缩小 2/3）
    :param max_dim: 可选最长边像素上限；若缩放后最长边仍超过该值，再整体缩到 max_dim
    :return: 输出文件路径
    """
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    if output_path is None:
        output_path = src.with_name(f"{src.stem}_sm{src.suffix}")
    out = Path(output_path)

    img = Image.open(src)
    # 统一按 RGB/RGBA 处理，避免带调色板/透明通道的 PNG 在 resize 后偏色或丢透明
    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    if has_alpha:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    w, h = img.size
    new_w = max(1, int(round(w * factor)))
    new_h = max(1, int(round(h * factor)))

    if max_dim and max(new_w, new_h) > max_dim:
        scale = max_dim / float(max(new_w, new_h))
        new_w = max(1, int(round(new_w * scale)))
        new_h = max(1, int(round(new_h * scale)))

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    fmt = SUFFIX_TO_FORMAT.get(out.suffix.lower())
    if fmt is None:
        # 未知后缀时尝试沿用原格式
        fmt = SUFFIX_TO_FORMAT.get(src.suffix.lower(), "PNG")
    # JPEG 不支持透明，转回 RGB
    if fmt == "JPEG" and resized.mode == "RGBA":
        resized = resized.convert("RGB")

    resized.save(output_path, fmt)
    print(
        f"Resized {w}x{h} -> {new_w}x{new_h} "
        f"(factor={factor}, max_dim={max_dim}) => {output_path}"
    )
    return str(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="等比缩小图片，用于插入钉钉文档前预处理（默认缩到 1/3）"
    )
    parser.add_argument("input", help="Input image file")
    parser.add_argument("output", nargs="?", default=None, help="Output image file (optional)")
    parser.add_argument(
        "--factor",
        type=float,
        default=1.0 / 3.0,
        help="缩放系数，默认 1/3（即等比小 2/3）",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=None,
        help="可选：缩放后最长边像素上限；超过则再整体缩到此值",
    )
    args = parser.parse_args()

    try:
        resize_image(args.input, args.output, args.factor, args.max_dim)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
