# note投稿の仕組み（方法2：GitHub Actions × Playwright）

## なぜこの構成か
- note.com に**公式の投稿APIは無く**、非公式APIは不安定（本文422・画像404・トークン30分失効を実測）。
- **Claudeの実行環境はブラウザ（Chromium）が一切のHTTPSに到達できない**（外向き通信がポリシープロキシ限定で、
  ブラウザがそのCAを信頼できず全サイトが接続リセット。TLS検証の無効化は環境ポリシーで禁止）。
- そこで、**記事生成＝Claudeルーチン／投稿＝GitHub Actions** に分離する（Xアカウント運用と同じ構成）。
  Actionsランナーはネットワーク制限が無く、Playwrightでブラウザを普通に動かせる。

```
[Claudeルーチン 07:30 JST] 生成→QA→サムネ→ commit/push（記事＋note_body.html）
        │
        ▼
[GitHub Actions note-publish] 07:45 JST or 手動 → Playwrightでnoteにログイン→投稿
```

## 有効化の手順（あなたの作業）

### 1. 長期有効なログインCookieを取得
- Chromeで note.com にログイン → F12 → Application → Cookies → `https://note.com`
- **`_note_session_v5` の Value 全体**（長い文字列。sidやJWTではない方）をコピー。
- ※ 以前いただいた `note_gql_auth_token`（JWT）は**30分で失効**するため日次運用には使えません。

### 2. GitHub Secrets / Variables に登録
- リポジトリ → Settings → Secrets and variables → Actions
  - **Secret** `NOTE_SESSION_COOKIE` = `_note_session_v5=＜長い値＞`（必要なら他Cookieも `; ` 区切りで）
  - （任意）**Variable** `NOTE_USERNAME` = `monoen_co_jp`

### 3. ワークフローをデフォルトブランチに載せる
- `schedule`（定時実行）は**デフォルトブランチ上のワークフローでのみ発火**します。
- このブランチ（`claude/note-auto-update-routine-xviq8e`）を main にマージすると、定時投稿が有効に。

### 4. まずテスト（DRY_RUN）
- Actions → **note-publish** → **Run workflow** → `dry_run=1`, `publish_mode=draft` で実行。
- 実行後、artifact **note-debug** のスクリーンショット（`01_editor.png`〜）を確認。
  - ログイン済みでエディタが開けているか、タイトル/本文が入っているか。
- note のUIに合わせて `scripts/note_playwright_post.py` の `# TUNE` 箇所（セレクタ）を微調整。
  - 初回は数回の調整が必要な想定です（noteのDOMは動的なため）。

### 5. 本番化
- テストで下書きが正しく作れたら、`dry_run=0`・`publish_mode=auto` に。
- 以後、毎朝 07:45 JST（`cron: 45 22 * * *` UTC）に自動投稿。QA=draftの記事は公開せず下書き止まり。

## Cookieの寿命と更新
- `_note_session_v5` は数週間で失効し得ます。投稿が急に `fallback_package` になったら、
  手順1で取り直して Secret を更新してください（`--whoami`相当の失敗＝Cookie切れの合図）。

## 正直な注意
- 非公式な自動化のため、**noteのUI変更・bot対策で壊れることがあります**（規約リスクも残ります）。
- 壊れている間も、Claudeルーチンは毎朝**完成パッケージ（`article.md`＋`note_body.html`＋`eyecatch.png`）**を
  生成・コミットし続けるので、`OPERATIONS.md` の手順で**手動投稿（約2分）**に切り替えられます。
