#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_eyecatch.py — アイキャッチ画像生成（OpenAI gpt-image-1）

- 英語プロンプトを受け取り gpt-image-1 で画像生成
- note 推奨の 1280x670（1.91:1）へ中央クロップ＆リサイズ
- APIキー無し / コスト上限超過 / 失敗 時はスキップして非ゼロ終了（記事は画像なしでも公開可）

使い方:
  python3 generate_eyecatch.py --prompt-file path/eyecatch_prompt.txt --out path/eyecatch.png
  python3 generate_eyecatch.py --prompt "Editorial hero image ..." --out path/eyecatch.png

環境変数:
  OPENAI_API_KEY           必須
  OPENAI_IMAGE_MODEL       既定 gpt-image-1
  OPENAI_IMAGE_QUALITY     high|medium|low（既定 medium）
  IMAGE_COST_CEILING_USD   1枚の見積コスト上限（既定 0.30）。超えたら生成しない。
"""
import argparse
import base64
import os
import sys
from pathlib import Path

# gpt-image-1 のおおよその1枚コスト見積（landscape 1536x1024）。正確な課金はOpenAIの明細を参照。
COST_ESTIMATE_USD = {"low": 0.02, "medium": 0.07, "high": 0.19}
GEN_SIZE = "1536x1024"       # 生成サイズ（横長）。これを1280x670へ整形。
TARGET_W, TARGET_H = 1280, 670


def _load_env():
    """ローカル検証用に scripts/.env があれば読む（本番はenv varを使う）。"""
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


def crop_to_note(src_bytes: bytes, out_path: Path):
    """1.91:1 に中央クロップして 1280x670 で保存。Pillow 必須。"""
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(src_bytes)).convert("RGB")
    w, h = img.size
    target_ratio = TARGET_W / TARGET_H
    ratio = w / h
    if ratio > target_ratio:            # 横に広い → 左右を切る
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:                               # 縦に広い → 上下を切る
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def main():
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file and Path(args.prompt_file).exists():
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    else:
        _fail("プロンプトがありません（--prompt か --prompt-file）")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _fail("OPENAI_API_KEY が未設定。画像はスキップします（記事は画像なしで公開可）。")

    quality = os.getenv("OPENAI_IMAGE_QUALITY", "medium").lower()
    if quality not in COST_ESTIMATE_USD:
        quality = "medium"
    ceiling = float(os.getenv("IMAGE_COST_CEILING_USD", "0.30"))
    est = COST_ESTIMATE_USD[quality]
    if est > ceiling:
        _fail(f"見積コスト ${est:.2f} > 上限 ${ceiling:.2f}（quality={quality}）。生成を中止。")

    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            size=GEN_SIZE,
            quality=quality,
            n=1,
        )
        b64 = resp.data[0].b64_json
        raw = base64.b64decode(b64)
    except Exception as e:
        _fail(f"画像API失敗: {e}")

    try:
        crop_to_note(raw, Path(args.out))
    except Exception as e:
        # 整形に失敗しても生画像を残す
        Path(args.out).with_suffix(".raw.png").write_bytes(raw)
        _fail(f"整形失敗（生画像を .raw.png で保存）: {e}")

    print(f"[eyecatch] OK: {args.out}  (model={model}, quality={quality}, est≈${est:.2f})")


if __name__ == "__main__":
    main()
