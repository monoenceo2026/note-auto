# STEP 4 プロンプト｜アイキャッチ（サムネ）設計 — GPT一発生成

背景も日本語テキストも **gpt-image-1 に一度に描かせます**（後処理での文字合成はしない＝ユーザー選択）。
`scripts/generate_eyecatch.py` に `--text`（フック）/`--eyebrow`（カテゴリ）/`--brand` を渡すと、
それらを「画像内に正確に描くテキスト」としてプロンプトへ埋め込みます。
`metadata.json` の `eyecatch_brief`（背景の主題）・`eyecatch_text`・`eyecatch_eyebrow` を使用。
最終出力 1280×670（1.91:1）。**フィードで目を引きつつブランドの品位を保つ**のが狙い。

## ⚠️ 文字化けの検証（必須）
画像モデルは稀に文字を崩します（特に英字・長い文）。**生成後に必ず画像を目視で読み**、
`--text`/`--eyebrow` と一字一句一致しているか確認する。崩れていたら**再生成（最大2回）**。
- 2回試しても英字が崩れる場合：`--eyebrow` を短く/簡単な語にする、または省略する。
- それでも崩れる場合：`--text` のみ（日本語は比較的安定）にする、最終的に画像なしでも公開可。
- 品質重視なら `OPENAI_IMAGE_QUALITY=high`（日本語の再現性が上がる／コスト増）。

## ブランドのビジュアル原則（背景画像）
- MONOENのコアアイデア「**無機物に、生命を。技術に、物語を。**」を視覚化する。
- 工業（金属・工具・工場）× 物語性（光・質感・静けさ・品格）の掛け合わせ。
- 和製LVMH＝**上質・ミニマル・エディトリアル**。安っぽいストックフォト感やコラージュ感を避ける。
- 実在の商品・ロゴ・工程を**具体的に再現しない**（誤認防止）。抽象・象徴表現にする。
- テキストは画像内に一発で描かせる。**被写体は片側（右など）に寄せ、反対側にテキスト用の静かで暗い面**を作る。

## トーン&マナー
- 配色：素材の質感を活かした落ち着いたトーン（鉄・真鍮・生成り・墨・自然光）。差し色は控えめ。
- 構図：横長1.91:1。被写体を片側に寄せ、テキスト側（見出しが乗る側）を暗く空ける。
- 照明：やわらかな自然光/スタジオ光。硬い影を避け、静謐で上質に。
- 文字：日本語ゴシックで太め・可読性重視。背景とのコントラストを確保。

## テーマ別モチーフの指針（例）
- ブランディング/リブランディング系 → 素材や道具が光の中で佇む静物、変化・磨きの象徴
- ライブコマース/EC/販路 → スタジオ的な光、繋がり・伝播を抽象化（線・波紋）、スマホは象徴的に
- 職人・現場・事例 → 手仕事の質感、工房の光と影（人物の顔は特定させない）
- 課題・データ・トレンド → 構造・グリッド・地図的抽象、知的で落ち着いた印象
- 海外・地域・共創 → 広がり・地平・結節点の抽象
- 思想・用語・FAQ → ミニマルな幾何・余白の効いたエディトリアル

## 出力（`eyecatch_prompt.txt` に英語で1つ＝背景の指示）

テンプレート（英語で具体化。**テキストはここに書かず**、`--text`/`--eyebrow` でスクリプトが追記する）:
```
Editorial hero image, 1.91:1 landscape, for a premium Japanese manufacturing/branding article.
Subject: <記事テーマを象徴する抽象/静物のモチーフ>.
Composition: place the subject on one side; keep the opposite side a calm, darker surface to hold a headline.
Style: refined, minimal, LVMH-like editorial, quiet and premium; material textures of <steel / brass / natural fiber>.
Lighting: soft directional light, gentle shadows, calm and sophisticated.
Mood: "giving life to the inorganic; giving story to technology."
Do not depict real identifiable products, brand logos, or real people's faces.
Color palette: muted, material-driven, restrained accent.
```

## 実行（GPT一発・テキスト込み）
```
python3 scripts/generate_eyecatch.py \
  --prompt-file <articleディレクトリ>/eyecatch_prompt.txt \
  --out <articleディレクトリ>/eyecatch.png \
  --text "<metadata.eyecatch_text>" \
  --eyebrow "<metadata.eyecatch_eyebrow>" \
  --brand "MONOEN"
```
- スクリプトが `--text`/`--eyebrow`/`--brand` を「画像内に正確に描く」指示としてプロンプトへ追記し、gpt-image-1が一発生成。
- **生成後に必ず画像を目視検証**（上の「文字化けの検証」）。崩れていたら再生成。
- 失敗・APIキー無し・コスト上限超過はスキップし、`eyecatch_prompt.txt` を残して警告（記事は画像なしでも公開可）。
