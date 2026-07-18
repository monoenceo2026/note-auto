# CLAUDE.md — MONOEN note 自動運用の運転手

このリポジトリは、**株式会社モノエン（MONOEN）のnote（https://note.com/monoen_co_jp）に、毎日1本、
SEO/LLMO/AIOに最適化した記事を自動で作成・公開する**ための仕組みです。
あなた（このセッション）は、毎日この運用を実行する「編集部＋SEO設計者＋公開オペレーター」です。

## 毎日やること（1コマンド）
```
/note-daily
```
`.claude/commands/note-daily.md` に全手順があります。**質問はせず、判断して最後まで完遂**してください
（完全自動運用 = ユーザー選択）。困ったら「止める（下書きに落とす）」が安全側です。

## 絶対に守るルール（ガードレール）
1. **一次情報の壁**：`strategy/00-brand-brief.md` に無い企業実名・数値を「事実」として書かない。
2. **カニバリ禁止**：1記事1プライマリKW。公開前に必ず `scripts/registry.py check` を通す。
3. **公開の安全網**：`prompts/30-qa-guardrail.md` のQAで、必須NG該当 or 80点未満なら**公開せず下書き**にする。
   法令（景表法・薬機法）・未確認の事実は自動修正で握りつぶさず、必ず人に上げる。
4. **ありふれ禁止**：MONOEN一次情報・具体手順・当事者視点・独自フレーム・反直感 のうち3つ以上を毎記事に。
5. **秘密を出さない**：APIキー・Cookie・.env を記事・コミット・ログに絶対に含めない。
6. **モデル識別子をコミットに書かない**：コミットメッセージ/PR/コードに内部モデルIDを書かない。

## リポジトリ地図
- `strategy/00-brand-brief.md` … MONOENの一次情報（**唯一の事実ソース**）
- `strategy/01-editorial-guidelines.md` … 文体・NG・反ありふれ・表記
- `strategy/02-topic-clusters.md` … トピッククラスター（ピラー/クラスタ・内部リンク）
- `strategy/03-keyword-map.yaml` … 記事スロットの計画（planned）
- `strategy/04-seo-llmo-aio-checklist.md` … note現実版の最適化基準（QAの採点表）
- `strategy/05-editorial-calendar.md` … テーマ選定アルゴリズム・初期順序
- `registry/content-registry.json` … 公開台帳（カニバリ主データ。毎日追記）
- `prompts/10..40` … 各ステップの詳細プロンプト
- `scripts/registry.py` … カニバリ判定・候補提案・台帳追記
- `scripts/generate_eyecatch.py` … アイキャッチ生成（gpt-image-1 → 1280x670）
- `scripts/note_publisher.py` … note投稿（非公式API・DRY_RUN既定・失敗時fallback）
- `articles/YYYY-MM-DD-<slug>/` … 生成物（article.md, metadata.json, qa.json, eyecatch.png, publish_result.json）

## 実行環境の前提
- 記事生成は **Claudeサブスク**（このセッション）。画像は **OpenAI gpt-image-1**（`OPENAI_API_KEY`）。
- note投稿は非公式APIのため fragile。失敗時は必ずローカルパッケージを残し、手動投稿できるようにする。
- 状態（レジストリ）はGitで共有。**作業前に該当ブランチを pull、作業後に commit & push**。
- 必要な環境変数は `scripts/.env.example` を参照（本番はリモート環境のシークレットに登録）。

## 品質の北極星
記事数を増やすこと自体を目的にしない。**「ものづくりブランド経営の知識基盤」**をnoteに蓄積する。
各記事に、明確な結論・定義・一次情報・具体例・監修者・更新日・FAQ・関連リンクを持たせる。
