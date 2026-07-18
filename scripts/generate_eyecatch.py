#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_eyecatch.py — アイキャッチ/サムネイル生成（OpenAI gpt-image-1 一発生成）

方針（ユーザー選択）:
  - 背景も日本語テキストも gpt-image-1 に「一気に」描かせる（後処理でのテキスト合成はしない）。
  - --text / --eyebrow / --brand を渡すと、それらを「画像内に正確に描くテキスト」として
    プロンプトへ埋め込む。
  - note 推奨 1280x670（1.91:1）へクロップして出力。
  - APIキー無し/コスト上限超過/失敗 時はスキップ（記事は画像なしでも公開可）。

使い方:
  python3 generate_eyecatch.py --prompt-file p.txt --out out.png \
      --text "技術はある。でも、伝わっていない。" --eyebrow "MANUFACTURING BRANDING" --brand MONOEN

環境変数:
  OPENAI_API_KEY / OPENAI_IMAGE_MODEL(既定 gpt-image-1) / OPENAI_IMAGE_QUALITY(high|medium|low)
  IMAGE_COST_CEILING_USD(既定 0.30)

注意: 画像モデルによる日本語テキストは、稀に字形が崩れることがあります。品質重視の場合は
      OPENAI_IMAGE_QUALITY=high を推奨（コストは上がります）。
"""
import argparse
import base64
import os
import sys
from pathlib import Path

COST_ESTIMATE_USD = {"low": 0.02, "medium": 0.07, "high": 0.19}
GEN_SIZE = "1536x1024"
TARGET_W, TARGET_H = 1280, 670


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


def build_text_block(text, eyebrow, brand):
    """画像内に正確に描かせる日本語テキストの指示を作る。"""
    lines = []
    lines.append(
        "IMPORTANT — render the following text directly ON the image as crisp, "
        "legible typography. Reproduce every character EXACTLY as written; do NOT "
        "translate, alter, omit, or add any characters. The Japanese must be perfectly accurate."
    )
    if eyebrow:
        lines.append(f'- Small kicker label (uppercase, letter-spaced, small), text: "{eyebrow}"')
    if text:
        disp = text.replace("\\n", " / ")
        lines.append(f'- Main headline (large, bold, Japanese, may wrap to 2 lines), text: "{disp}"')
    if brand:
        lines.append(f'- Wordmark in a bottom corner (small, refined), text: "{brand}"')
    lines.append(
        "Typography: elegant modern sans-serif (Japanese Gothic for the Japanese text). "
        "Place the text over a calm, darker area of the composition with strong contrast so it is "
        "easily readable at thumbnail size. Left-aligned, generous margins, premium editorial layout. "
        "Keep it minimal and on-brand — do NOT make it look like a loud advertisement."
    )
    return "\n".join(lines)


def crop_to_note(src_bytes: bytes, out_path: Path):
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
    img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def main():
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", help="画像内に描く日本語フック（\\n 可）")
    ap.add_argument("--eyebrow", help="小見出し（英字カテゴリ推奨）")
    ap.add_argument("--brand", default="MONOEN")
    args = ap.parse_args()

    if args.prompt:
        base = args.prompt
    elif args.prompt_file and Path(args.prompt_file).exists():
        base = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    else:
        _fail("プロンプトがありません（--prompt か --prompt-file）")

    prompt = base
    if args.text or args.eyebrow:
        prompt = base + "\n\n" + build_text_block(args.text, args.eyebrow, args.brand)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _fail("OPENAI_API_KEY が未設定。画像はスキップします。")

    quality = os.getenv("OPENAI_IMAGE_QUALITY", "high").lower()
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
        crop_to_note(raw, Path(args.out))
    except Exception as e:
        Path(args.out).with_suffix(".raw.png").write_bytes(raw)
        _fail(f"整形失敗（生画像を .raw.png で保存）: {e}")

    txt = "テキスト入り一発生成" if (args.text or args.eyebrow) else "テキストなし"
    print(f"[eyecatch] OK: {args.out}  ({model}/{quality}, {txt}, est≈${est:.2f})")


if __name__ == "__main__":
    main()
