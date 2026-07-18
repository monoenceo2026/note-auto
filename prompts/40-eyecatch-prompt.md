# STEP 4 プロンプト｜アイキャッチ画像プロンプト設計（gpt-image-1）

`metadata.json` の `eyecatch_brief` と記事内容から、**gpt-image-1 用の英語プロンプト**を1つ作ります。
生成は `scripts/generate_eyecatch.py` が行い、1280×670（1.91:1）に整形します。

## ブランドのビジュアル原則
- MONOENのコアアイデア「**無機物に、生命を。技術に、物語を。**」を視覚化する。
- 工業（金属・工具・工場）× 物語性（光・質感・静けさ・品格）の掛け合わせ。
- 和製LVMH＝**上質・ミニマル・エディトリアル**。安っぽいストックフォト感やコラージュ感を避ける。
- 実在の商品・ロゴ・工程を**具体的に再現しない**（誤認防止）。抽象・象徴表現にする。
- **テキストは入れない**（noteのタイトルが上に乗る前提。文字化けも防ぐ）。

## トーン&マナー
- 配色：素材の質感を活かした落ち着いたトーン（鉄・真鍮・生成り・墨・自然光）。差し色は控えめ。
- 構図：横長1.91:1。被写体は中央〜やや左、右側に余白（タイトルが乗る想定）。
- 照明：やわらかな自然光/スタジオ光。硬い影を避け、静謐で上質に。
- 画角：マクロ〜寄りのエディトリアル。俯瞰の平置き（フラットレイ）も可。

## テーマ別モチーフの指針（例）
- ブランディング/リブランディング系 → 素材や道具が光の中で佇む静物、変化・磨きの象徴
- ライブコマース/EC/販路 → スタジオ的な光、繋がり・伝播を抽象化（線・波紋）、スマホは象徴的に
- 職人・現場・事例 → 手仕事の質感、工房の光と影（人物の顔は特定させない）
- 課題・データ・トレンド → 構造・グリッド・地図的抽象、知的で落ち着いた印象
- 海外・地域・共創 → 広がり・地平・結節点の抽象
- 思想・用語・FAQ → ミニマルな幾何・余白の効いたエディトリアル

## 出力（`eyecatch_prompt.txt` に英語で1つ）

テンプレート（英語で具体化して書く）:
```
Editorial hero image, 1.91:1 landscape, for a premium Japanese manufacturing/branding article.
Subject: <記事テーマを象徴する抽象/静物のモチーフ>.
Style: refined, minimal, LVMH-like editorial, quiet and premium; material textures of <steel / brass / natural fiber / ink>.
Lighting: soft natural light, gentle shadows, calm and sophisticated.
Composition: subject center-left, clean negative space on the right for a title overlay.
Mood: "giving life to the inorganic; giving story to technology."
No text, no logos, no readable brand marks, do not depict real identifiable products or real people's faces.
Color palette: muted, material-driven, restrained accent.
```

## 実行
```
python3 scripts/generate_eyecatch.py \
  --prompt-file <articleディレクトリ>/eyecatch_prompt.txt \
  --out <articleディレクトリ>/eyecatch.png
```
- 失敗・APIキー無し・コスト上限超過の場合はスキップし、`eyecatch_prompt.txt` を残して警告（記事は画像なしでも公開可、ただしメタに記録）。
