#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_eyecatch.py — アイキャッチ/サムネイル生成（OpenAI gpt-image-1 ＋ 日本語テキスト合成）

方針:
  - 背景は gpt-image-1 で「上質・ミニマル・ブランド準拠」に生成（テキストは入れさせない=文字化け回避）
  - その上に Pillow で日本語テキスト（フック＋カテゴリ＋MONOENワードマーク）を高解像で合成
    → note のフィードで目を引く「クリックしたくなるサムネ」に。ブランドは崩さない。
  - note 推奨 1280x670（1.91:1）で出力。
  - APIキー無し/コスト上限超過/失敗 時はスキップ（記事は画像なしでも公開可）。

使い方:
  python3 generate_eyecatch.py --prompt-file p.txt --out out.png \
      --text "価格で戦わない\n製造業ブランディング" --eyebrow "MANUFACTURING BRANDING"
  （--text 未指定なら従来どおりテキストなしの静物画像）

環境変数:
  OPENAI_API_KEY / OPENAI_IMAGE_MODEL(既定 gpt-image-1) / OPENAI_IMAGE_QUALITY(high|medium|low)
  IMAGE_COST_CEILING_USD(既定 0.30)
  EYECATCH_FONT      日本語フォントパス（既定: IPAPGothic）
  EYECATCH_ACCENT    アクセント色 hex（既定 #C8A96A ブラス）
"""
import argparse
import base64
import os
import sys
from pathlib import Path

COST_ESTIMATE_USD = {"low": 0.02, "medium": 0.07, "high": 0.19}
GEN_SIZE = "1536x1024"
TARGET_W, TARGET_H = 1280, 670

FONT_CANDIDATES = [
    os.getenv("EYECATCH_FONT", ""),
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]
ACCENT = os.getenv("EYECATCH_ACCENT", "#C8A96A")


def _load_env():
    try:
        from dotenv import load_dotenv
        env = Path(__file__).resolve().parent / ".env"
        if env.exists():
            load_dotenv(env)
    except Exception:
        pass


def _fail(msg, code=2):
    print(f"[eyecatch] SKIP: {msg}", file=sys.stderr)
    sys.exit(code)


def _font_path():
    for p in FONT_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------- #
# 画像整形
# --------------------------------------------------------------------------- #
def crop_to_note(src_bytes: bytes):
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(src_bytes)).convert("RGB")
    w, h = img.size
    tr = TARGET_W / TARGET_H
    r = w / h
    if r > tr:
        nw = int(h * tr); left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / tr); top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)


def _wrap(draw, text, font, maxw):
    """日本語向け：明示改行を尊重しつつ、幅に収まるよう文字単位で折り返す。"""
    lines = []
    for raw in text.replace("\\n", "\n").split("\n"):
        if not raw:
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if draw.textlength(cur + ch, font=font) <= maxw:
                cur += ch
            else:
                lines.append(cur); cur = ch
        if cur:
            lines.append(cur)
    return lines[:3]  # 最大3行


def overlay_thumbnail(img, hook, eyebrow=None, brand="MONOEN"):
    """プレミアムな下部スクリム＋日本語テキストを合成。"""
    from PIL import Image, ImageDraw, ImageFont
    fpath = _font_path()
    if not fpath:
        print("[eyecatch] WARN: 日本語フォントが見つからずテキスト合成をスキップ", file=sys.stderr)
        return img

    img = img.convert("RGBA")
    W, H = img.size
    accent = _hex(ACCENT)
    margin = 64

    # --- 下部グラデーションスクリム（可読性確保・上品に）---
    scrim_h = int(H * 0.66)
    grad = Image.new("L", (1, scrim_h), 0)
    px = grad.load()
    for y in range(scrim_h):
        px[0, y] = int(238 * (y / scrim_h) ** 1.5)
    grad = grad.resize((W, scrim_h))
    scrim = Image.new("RGBA", (W, scrim_h), (10, 11, 13, 255))
    scrim.putalpha(grad)
    img.alpha_composite(scrim, (0, H - scrim_h))

    draw = ImageDraw.Draw(img)

    # フォントサイズ（フック文字数で自動調整）
    hook_size = 84 if len(hook.replace("\\n", "").replace("\n", "")) <= 12 else (72 if len(hook) <= 20 else 60)
    hook_font = ImageFont.truetype(fpath, hook_size)
    eb_font = ImageFont.truetype(fpath, 26)
    brand_font = ImageFont.truetype(fpath, 28)

    maxw = int(W * 0.80)
    lines = _wrap(draw, hook, hook_font, maxw)
    line_h = int(hook_size * 1.28)

    # レイアウト：下から wordmark → hook → eyebrow の順に積む
    y_brand = H - margin - 30
    hook_block_h = line_h * len(lines)
    y_hook_bottom = y_brand - 34
    y_hook_top = y_hook_bottom - hook_block_h
    y_eyebrow = y_hook_top - 46

    # eyebrow（小さめ・字間広め・アクセント色）＋ 直下に細い罫
    if eyebrow:
        ex = margin
        for chx in eyebrow.upper():
            draw.text((ex, y_eyebrow), chx, font=eb_font, fill=accent + (255,))
            ex += draw.textlength(chx, font=eb_font) + 6
        draw.line([(margin, y_eyebrow + 40), (margin + 300, y_eyebrow + 40)],
                  fill=accent + (180,), width=2)

    # 左端の縦アクセントバー（エディトリアルなアクセント）
    draw.rectangle([margin - 22, y_hook_top + 6, margin - 14, y_hook_bottom - 6],
                   fill=accent + (255,))

    # フック本文（微かな影で可読性を上げつつ、太めに見せる）
    y = y_hook_top
    for ln in lines:
        draw.text((margin + 2, y + 2), ln, font=hook_font, fill=(0, 0, 0, 120))          # shadow
        draw.text((margin, y), ln, font=hook_font, fill=(245, 245, 242, 255),
                  stroke_width=1, stroke_fill=(245, 245, 242, 255))                        # faux-bold
        y += line_h

    # ワードマーク（MONOEN・字間広め・控えめな白）
    bx = margin
    for chx in brand:
        draw.text((bx, y_brand), chx, font=brand_font, fill=(255, 255, 255, 210))
        bx += draw.textlength(chx, font=brand_font) + 5

    return img.convert("RGB")


# --------------------------------------------------------------------------- #
def main():
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", help="サムネのフック文（\\n で改行可）。未指定ならテキストなし")
    ap.add_argument("--eyebrow", help="カテゴリ等の小見出し（英字推奨）")
    ap.add_argument("--brand", default="MONOEN")
    args = ap.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file and Path(args.prompt_file).exists():
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    else:
        _fail("プロンプトがありません（--prompt か --prompt-file）")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _fail("OPENAI_API_KEY が未設定。画像はスキップします。")

    quality = os.getenv("OPENAI_IMAGE_QUALITY", "medium").lower()
    if quality not in COST_ESTIMATE_USD:
        quality = "medium"
    ceiling = float(os.getenv("IMAGE_COST_CEILING_USD", "0.30"))
    est = COST_ESTIMATE_USD[quality]
    if est > ceiling:
        _fail(f"見積コスト ${est:.2f} > 上限 ${ceiling:.2f}（quality={quality}）。中止。")

    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.images.generate(model=model, prompt=prompt, size=GEN_SIZE,
                                       quality=quality, n=1)
        raw = base64.b64decode(resp.data[0].b64_json)
    except Exception as e:
        _fail(f"画像API失敗: {e}")

    try:
        img = crop_to_note(raw)
        if args.text:
            img = overlay_thumbnail(img, args.text, args.eyebrow, args.brand)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "PNG", optimize=True)
    except Exception as e:
        Path(args.out).with_suffix(".raw.png").write_bytes(raw)
        _fail(f"整形/合成失敗（生画像を .raw.png で保存）: {e}")

    txt = "＋テキスト合成" if args.text else "テキストなし"
    print(f"[eyecatch] OK: {args.out}  ({model}/{quality}, {txt}, est≈${est:.2f})")


if __name__ == "__main__":
    main()
