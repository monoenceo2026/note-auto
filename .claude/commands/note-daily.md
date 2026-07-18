---
description: MONOENのnoteに、SEO/LLMO/AIO最適化記事を1本、自動生成→QA→公開まで実行する日次ルーチン
---

# /note-daily — 日次自動運用（無人・完全自動）

あなたはMONOEN編集部です。**質問せず、判断して最後まで完遂**します。困ったら安全側（下書きに落とす）。
各ステップの詳細は `prompts/` を参照。ガードレールは `CLAUDE.md` を厳守。

---

## STEP 0. 準備

1. リポジトリのルートで作業。作業前に最新状態へ：
   ```
   git fetch origin claude/note-auto-update-routine-xviq8e
   git checkout claude/note-auto-update-routine-xviq8e
   git pull --ff-only origin claude/note-auto-update-routine-xviq8e || true
   ```
2. 依存をインストール（未導入なら）：
   ```
   python3 -m pip install -r scripts/requirements.txt
   ```
3. 今日の日付（JST）を確認し、記事ディレクトリを作る：
   `articles/<YYYY-MM-DD>-<英数slug>/`（slugはテーマ確定後でよい）。
4. 環境変数を確認：`OPENAI_API_KEY`（画像）, `NOTE_SESSION_COOKIE`/`PUBLISH_MODE`/`DRY_RUN`（公開）。
   無くても止めない（画像スキップ・公開はfallback）。

## STEP 1. テーマ選定（`prompts/10-theme-selection.md`）
1. `python3 scripts/registry.py suggest --top 8` で候補を取得。
2. **WebSearch でトレンド分析**（制度・季節・業界・MONOENの実イベント）。各候補に trend_score(0-3) と**出典**を付与。
3. 最終スコア = base_score + trend_score。最上位を選定。トレンド新規なら keyword-map に `T-YYYYMMDD` で追記。
4. `python3 scripts/registry.py check "<primary_kw>" --intent <intent>` で最終カニバリ確認。
   - `conflict` → 次点へ。`warn` → 差別化を1文で言えるなら可。
5. `articles/.../selection.json` を書く（primary_kw, intent, trend_rationale=出典付き, differentiator, internal_link候補）。

## STEP 2. 記事生成（`prompts/20-article-generation.md`）
1. 必読：`strategy/00-brand-brief.md` / `01-editorial-guidelines.md` / `04-seo-llmo-aio-checklist.md` / `02-topic-clusters.md`。
2. 必要に応じ WebSearch で事実・統計・制度を確認（**出典を控える**）。**brand-briefに無い実名/数値は事実として書かない**。
3. 逆ピラミッド＋直答構造で 3,000〜5,000字。反ありふれ要素3つ以上。FAQ・要点まとめ・監修・内部リンク・CTAを含める。
4. 出力：`article.md`（1行目 `# タイトル`）と `metadata.json`（`prompts/20`の形）。
   - `internal_links` は `registry` の**公開済みnote_url**のみ。無ければ空でよい。

## STEP 3. アイキャッチ生成（GPT一発サムネ／`prompts/40-eyecatch-prompt.md`）
1. `eyecatch_prompt.txt`（英語・背景の指示・被写体は片側／反対側を暗く空ける・実在商品を再現しない）を作る。
2. 生成（`metadata.json` の `eyecatch_text`/`eyecatch_eyebrow` を渡す。テキストも画像内に一発で描かせる）：
   ```
   OPENAI_IMAGE_QUALITY=high python3 scripts/generate_eyecatch.py \
     --prompt-file articles/.../eyecatch_prompt.txt \
     --out articles/.../eyecatch.png \
     --text "<eyecatch_text>" --eyebrow "<eyecatch_eyebrow>" --brand "MONOEN"
   ```
3. **文字化け検証（必須）**：生成した `eyecatch.png` を**自分の目（画像読み取り）で確認**し、
   `eyecatch_text` と `eyecatch_eyebrow` が**一字一句正しく**描かれているか判定。
   - 崩れていたら**再生成（最大2回）**。なお崩れる場合は `--eyebrow` を短く/省略、または `--text` のみに。
   - それでもダメなら画像なしで継続（metadataに `eyecatch_status:"skipped"` を記録）。
   失敗/キー無し/コスト上限超過ならスキップ（記事は画像なしでも可）。

## STEP 4. 公開前QA（`prompts/30-qa-guardrail.md`）★安全網
1. `article.md` と `metadata.json` を厳しく審査し、`qa.json` を書く（decision, total_score, must_ng_hits, fix_instructions）。
2. `decision=="draft"` かつ 原因が軽微（法令・事実系でない）なら、fix_instructionsに従い **article.md を1回だけ修正して再採点**。
3. 法令・未確認事実の必須NGは自動修正で消さず、`draft` のまま人に上げる。

## STEP 5. パッケージ化（`scripts/note_publisher.py`）＝noteへは触れない
```
python3 scripts/note_publisher.py --dir articles/<今日のディレクトリ>
```
- このClaude環境は**ブラウザが使えず、noteへ確実に投稿できない**ため、ここでは
  **note貼り付け用HTML（`note_body.html`）＋パッケージのみ生成**する（既定 PUBLISH_MODE=package）。
- 実際のnote投稿は **GitHub Actions（`.github/workflows/note-publish.yml` → `note_playwright_post.py`）** が担当。
  ワークフローが有効（デフォルトブランチ＋`NOTE_SESSION_COOKIE` secret）なら、生成後に自動/定時で投稿される。
- `publish_result.json` に package の status が入る（日次処理は止めない）。

## STEP 6. 台帳更新（カニバリ制御の要）
1. `metadata.json` + `qa.json` + `publish_result.json` から台帳エントリを作り、一時JSONに保存。
   必須：id, date, title, primary_kw, intent, pillar, type, status(published/draft/hold), note_url, qa_score, trend_rationale, internal_links, summary。
   - `publish_result.status=="published"` → status="published"。それ以外（draft/fallback/package/dry_run）→ status="draft" or "hold"。
2. 追記：`python3 scripts/registry.py add --file <一時JSON>`。
3. `keyword-map.yaml` の該当スロット status を published（公開時）へ更新。

## STEP 7. コミット & プッシュ
```
git add -A
git commit -m "note: <YYYY-MM-DD> <タイトル>（<status>）"
git push -u origin claude/note-auto-update-routine-xviq8e   # 失敗時は 2s,4s,8s,16s でリトライ
```
- **秘密（.env/Cookie/キー）を絶対にコミットしない**（.gitignore済みだが確認）。
- 生成物（article.md, metadata.json, qa.json, eyecatch.png, publish_result.json）はコミットしてよい。

## STEP 8. 通知（ユーザーへ結果報告）
以下を1つのメッセージにまとめてユーザーに通知（`PushNotification` が使えれば使用、無ければ本文出力）：
- ✅/⚠️ 見出し（published なら✅、draft/fallback なら⚠️要対応）
- タイトル / ピラー・ID / primary_kw
- QAスコア と decision
- テーマ選定の根拠（trend_rationale・出典）
- note_url（published時）／「手動投稿が必要」（fallback_package時、手順は `OPERATIONS.md`）
- 画像：あり/なし

### 要対応（⚠️）のときの明示
- `decision=draft` … QAで基準未達。fix_instructions を要約して「何を直せば公開できるか」を伝える。
- `fallback_package` … note投稿に失敗。ローカルの完成パッケージ（article.md＋eyecatch.png）を手動で貼る手順を案内。

---

## 失敗時の原則
- どのステップで失敗しても、**そこまでの成果物をコミットし、状況をユーザーに通知**して終える（沈黙しない）。
- 記事の質・法令・カニバリに少しでも不安があれば **公開しない**（下書き＝安全）。
- 同じ失敗が続く場合は、原因の仮説と必要な対応（例：Cookie再取得、endpoint更新）を通知する。
