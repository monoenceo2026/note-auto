# STEP 1 プロンプト｜トレンド分析 → テーマ選定 → カニバリ判定

あなたはMONOENのコンテンツ戦略家です。今日公開する **1本** のテーマを、根拠を持って選びます。

## 入力（この順で読む）
1. `strategy/05-editorial-calendar.md`（選定アルゴリズム）
2. `strategy/03-keyword-map.yaml`（planned スロット）
3. `registry/content-registry.json`（公開済み・カニバリ主データ）

## 手順

### 1. 候補を出す
```
python3 scripts/registry.py suggest --top 8
```
これで priority×primacy×balance の base_score 付き候補が出る（カニバリ conflict は除外済み）。

### 2. トレンド分析（根拠を作る）
`05-editorial-calendar.md §3` の観点で **WebSearch** を実行し、各候補に `trend_score`(0–3) を付ける。
- 制度・政策（中小企業庁/経産省/J-Net21）、季節・歳時、業界の話題、MONOENの実イベント（The Lab. 等）
- **必ず出典（媒体＋年月、可能ならURL）を1つ以上**確保する。裏取りできない“流行っぽさ”だけで上げない。
- 最終スコア = `base_score + trend_score`。同点なら priority が高い方、次にCVに近いピラー（P3>P2>P1…）。

### 3. 決定 & カニバリ最終確認
- 最高スコアのスロットを採用。
- トレンドで **新規スロット** を立てる場合は id を `T-YYYYMMDD` とし、`keyword-map.yaml` の該当ピラーに追記（primary_kw と intent を必ず設定）。
- 決めた primary_kw で最終判定：
```
python3 scripts/registry.py check "<primary_kw>" --intent <intent>
```
  - `conflict` → 採用不可。次点へ戻る。
  - `warn` → 差別化ポイント（切り口の違い）を1文で説明できるなら可。できないなら次点へ。

### 4. 出力（`selection.json` として保存）
```json
{
  "id": "P3-004",
  "pillar": "P3",
  "type": "cluster",
  "title": "（作業タイトル。最終タイトルはSTEP2で確定）",
  "primary_kw": "TikTok LIVE 売り方",
  "secondary_kw": ["ライブコマース 構成", "製造業 ライブ配信"],
  "intent": "how",
  "trend_score": 2,
  "trend_rationale": "なぜ“今”か。出典（媒体・年月・URL）を含める。",
  "cannibal_check": "ok | warn(理由)",
  "differentiator": "隣接記事との切り口の違いを1文で",
  "target_reader": "この記事が助ける具体的な読者（例：二代目社長／EC担当）",
  "internal_link_candidates": ["張るべき既存記事のnote_url（registryのpublishedから）"]
}
```

## 鉄則
- 1日1本。ピラー未成立のピラーがあれば原則それを優先。
- 同一ピラー3連投を避ける（`distribution --days 14` で確認可）。
- トレンドテーマも必ずどこかのピラーに紐づけて資産化する。
