# OPERATIONS.md — 日々の運用・トラブル対応

---

## 1. 毎日の見方（通知の読み方）

毎朝、ルーチンが結果を通知します。見るべきは1点：**status**。

| status | 意味 | あなたの対応 |
|---|---|---|
| ✅ `published` | note に自動公開済み | 基本は不要。URLを開いて軽く目視するだけ |
| ⚠️ `draft`（QA不合格） | QAで基準未達→**公開せず下書き** | 通知の「fix指示」を見て、直すか見送るか判断 |
| ⚠️ `fallback_package` | note投稿に失敗（Cookie切れ等） | §3 手動投稿 or Cookie更新 |
| `package_only` | `PUBLISH_MODE=package`（手動運用） | §3 手動投稿 |
| `dry_run_ok` | 試運転（未投稿） | 内容確認。本番化は `DRY_RUN=0` |

生成物は `articles/<日付>-<slug>/` にすべて残ります（article.md / metadata.json / qa.json / eyecatch.png / publish_result.json）。

---

## 2. 記事を手動で見たい / 直したい

- 本文：`articles/<日付>-<slug>/article.md`
- note貼り付け用HTML：`articles/<日付>-<slug>/note_body.html`
- 画像：`articles/<日付>-<slug>/eyecatch.png`
- QAの指摘：`articles/<日付>-<slug>/qa.json` の `fix_instructions`

直したら、再度QA〜公開だけ流したい場合はClaudeに「この記事を再QAして公開して」と指示してください。

---

## 3. 手動で note に投稿する（fallback / package のとき）

1. note で「新規投稿」→「テキスト」。
2. `article.md` の1行目（`# ...`）を**タイトル**に。
3. 本文は `article.md` の2行目以降を貼り付け（見出しは note の大見出し/小見出しに整形）。
   - きれいに貼りたい場合は `note_body.html` を参考に、見出し・箇条書き・太字を再現。
4. アイキャッチに `eyecatch.png` を設定。
5. `metadata.json` の `hashtags` をハッシュタグに設定。
6. 公開。**公開後、その note のURLを台帳に反映**しておくと内部リンクとカニバリ精度が上がります：
   - Claudeに「この記事のnote_urlを `<URL>` にしてレジストリ更新して」と伝える（`scripts/registry.py` が扱います）。

---

## 4. よくあるトラブル

### 画像が生成されない
- `OPENAI_API_KEY` 未設定 / 残高不足 / ネットワーク不通 / コスト上限超過。
- `publish_result.json` や実行ログの `[eyecatch] SKIP: ...` に理由が出ます。記事は画像なしで継続します。

### 公開が急に `fallback_package` になった
- 多くは **Cookieの期限切れ**。[`SETUP.md`](./SETUP.md) STEP2 で再取得し `NOTE_SESSION_COOKIE` を更新。
- `--whoami` で有効性を確認：`python3 scripts/note_publisher.py --dir <記事dir> --whoami`。
- それでも失敗する場合は **noteのAPI仕様変更**の可能性。`scripts/note_publisher.py` 冒頭の `ENDPOINTS` を、
  ブラウザの開発者ツール（Network、投稿操作時のリクエスト）で確認して更新（Claudeに調査を依頼可）。

### 同じテーマ・似た記事が出そう
- カニバリ制御は `registry/content-registry.json` を主データにします。**手動投稿分もURL登録**しておくと精度が上がります。
- `python3 scripts/registry.py check "<KW>" --intent <intent>` でいつでも重複チェックできます。

### 内部リンクが張られない
- 公開初期は登録済み記事が少ないため。台帳が育つと自動で増えます。手動投稿分のURL登録が効きます。

---

## 5. コスト感

- **記事生成**：Claudeサブスクの範囲（追加API課金なし）。
- **アイキャッチ**：OpenAI gpt-image-1。1枚あたりの目安 low≈$0.02 / medium≈$0.07 / high≈$0.19（横長・概算）。
  毎日1枚なら medium で月 **$2〜3** 程度。`IMAGE_COST_CEILING_USD` で1枚上限、OpenAI側でも月次上限を設定推奨。

---

## 6. 運用の育て方（3か月ごとの見直し）

- 検索実績（Google Search Console）と商談化状況を見て、`strategy/05-editorial-calendar.md` の**ピラー配分**を調整。
- 伸びている/惜しいキーワードを `strategy/03-keyword-map.yaml` に追加。
- ヒアリングシートの目標（6か月/12か月）に対する進捗を確認。
- 品質が安定したら、QAの閾値やトーンを微調整（`strategy/04-...` の採点表）。

---

## 7. 公開の慎重度を変える
`PUBLISH_MODE` を切り替えるだけ（環境変数）：
- `auto` … QA合格で自動公開（現在の設定）
- `draft` … note下書きまで（公開はあなた）
- `package` … noteに触れず完成パッケージのみ

不安な時期は `draft`、慣れたら `auto`、といった運用も可能です。

---

## 8. 規約・コンプライアンスの最終責任
- note自動公開は**非公式APIを用いる方法**で、規約・仕様変更のリスクがあります（[`README.md`](./README.md) 参照）。
- 景表法・薬機法・実名/数値の公開許可など、**最終的な責任は人間側**にあります。
  QAは強力な安全網ですが万能ではありません。初期は毎日の通知確認を続け、必要に応じて `draft` 運用にしてください。
