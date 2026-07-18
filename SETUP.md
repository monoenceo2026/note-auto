# SETUP.md — セットアップ手順（あなたの作業）

所要 20〜30分。上から順にやれば完了します。分からなければこのリポジトリ上でClaudeに聞いてください。

---

## 前提：この仕組みが動く場所
このルーチンは **Claude Code の実行環境（クラウド）** の中で、毎朝スケジュール起動します。
記事生成はあなたの **Claudeサブスク**、画像は **OpenAI API** を使います。
環境・スケジュール・ネットワークの考え方は公式ドキュメントも参照してください：
https://code.claude.com/docs/en/claude-code-on-the-web

---

## STEP 1. OpenAI APIキーの用意（画像生成・必須）

1. https://platform.openai.com/ でアカウント作成・**支払い方法を登録**（少額でOK。目安は §5 コスト参照）。
2. API Keys で新しいキーを発行（`sk-...`）。
3. **課金上限（Usage limits）を設定**しておくと安心（例：月 $10 など）。
4. このキーを、次のSTEP 3で環境シークレット `OPENAI_API_KEY` に登録します。

---

## STEP 2. note のログインCookieを取得（完全自動公開・必須）

> ⚠️ Cookieは「あなたのnoteにログインした状態」を表す**機密情報**です。第三者に渡さない・リポジトリに置かない。
> 本システムは `.gitignore` でコミットを防いでいますが、取り扱いに注意してください。

**取得手順（PCのChrome/Edgeを想定）**
1. ブラウザで https://note.com にログイン（アカウント：`monoen_co_jp`）。
2. `F12`（または右クリック→検証）で**開発者ツール**を開く。
3. 上部タブ **Application**（Edgeは「アプリケーション」）→ 左メニュー **Cookies** → `https://note.com` を選択。
4. 次のCookieの **Value** をコピー：
   - `_note_session_v5`（**必須**）
   - `note_gql_auth_token`（あれば併せて）
5. 下記の形式で1行にまとめ、STEP 3で `NOTE_SESSION_COOKIE` に登録：
   ```
   _note_session_v5=＜値＞; note_gql_auth_token=＜値＞
   ```
   （`note_gql_auth_token` が無ければ `_note_session_v5=＜値＞` だけでも可）

**補足**
- Cookieは**期限切れ**になることがあります。公開が急に `fallback_package`（＝失敗）になったら、再取得して更新してください（[`OPERATIONS.md`](./OPERATIONS.md) §3）。
- `NOTE_USERNAME=monoen_co_jp` も一緒に登録します（記事URL生成に使用）。

---

## STEP 3. 環境シークレット / 環境変数の登録

Claude Code の環境設定（Environment の環境変数／シークレット）に、以下を登録します。
（登録画面の場所は上記ドキュメント参照。**シークレットはコミットされません**。）

| キー | 値 | 必須 | 備考 |
|---|---|---|---|
| `OPENAI_API_KEY` | `sk-...` | ✅ | STEP1のキー |
| `OPENAI_IMAGE_QUALITY` | `medium` | 任意 | high/medium/low。コストと品質の調整 |
| `IMAGE_COST_CEILING_USD` | `0.30` | 任意 | 1枚の見積上限。超えたら画像スキップ |
| `NOTE_SESSION_COOKIE` | `_note_session_v5=...; ...` | ✅(自動公開) | STEP2のCookie |
| `NOTE_USERNAME` | `monoen_co_jp` | ✅(自動公開) | |
| `PUBLISH_MODE` | `auto` | ✅ | auto / draft / package |
| `DRY_RUN` | `1`（最初）→ `0`（本番） | ✅ | 最初はテスト、確認後に本番 |
| `PUBLISH_TIME_JST` | `08:00` | 任意 | 記事メタの公開予定時刻 |

> ローカルで試す場合のみ、`scripts/.env.example` を `scripts/.env` にコピーして値を入れられます（`.env` はコミットされません）。本番はシークレットを使ってください。

---

## STEP 4. ネットワーク到達性の確認

ルーチンのセッションから、以下へ **HTTPSで到達できる**必要があります。
- `api.openai.com`（画像生成）
- `note.com`（自動公開）
- 検索（WebSearch）＝トレンド分析・事実確認

環境のネットワークポリシーで外部通信が絞られている場合は、上記ドメインを許可してください
（設定方法はドキュメント参照）。到達できないと、画像や公開が `fallback`／`skip` になります（記事生成自体は継続）。

---

## STEP 5. 試運転（DRY_RUN）→ 本番切替

### 5-1. まずドライラン
`DRY_RUN=1` のまま、手動で1回実行して挙動を確認します（このリポジトリ上のClaudeに）：
```
/note-daily
```
- `articles/<日付>-<slug>/` に article.md / metadata.json / qa.json / eyecatch.png / publish_result.json ができる。
- `publish_result.json` の status が `dry_run_ok` になる（実際にはnoteに投稿していない）。
- 記事の中身・アイキャッチ・QAスコアを確認する。

### 5-2. Cookie有効性チェック（任意）
```
python3 scripts/note_publisher.py --dir articles/<日付>-<slug> --whoami
```
→ `whoami_ok` なら Cookie は有効。`whoami_ng` なら STEP2を再取得。

### 5-3. 本番へ
記事品質・画像・QAに問題がなければ、`DRY_RUN` を **`0`** に変更。
翌朝 07:30 JST から、**生成→QA→自動公開**が始まります。

---

## STEP 6. スケジュール（ルーチン）について
- 毎朝 **07:30 JST**（=公開目標8:00に間に合う時刻）に起動するよう設定します（この登録はClaude側で実施）。
- 起動時刻を変えたい場合は「毎朝◯時に変更して」と伝えてください。
- スケジュールが動くには、この実行環境が利用可能な状態である必要があります（環境が長期間停止すると起動しません）。

---

## 完了チェック
- [ ] `OPENAI_API_KEY` 登録済み・課金上限設定済み
- [ ] `NOTE_SESSION_COOKIE` / `NOTE_USERNAME` 登録済み（完全自動公開の場合）
- [ ] `PUBLISH_MODE=auto`、まず `DRY_RUN=1`
- [ ] ネットワークが openai / note に到達可
- [ ] `/note-daily` のドライランで成果物を確認した
- [ ] 問題なければ `DRY_RUN=0` に変更

運用開始後の「毎日の見方」「手動投稿」「トラブル対応」は [`OPERATIONS.md`](./OPERATIONS.md) へ。
