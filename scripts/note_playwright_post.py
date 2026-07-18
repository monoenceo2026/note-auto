#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
note_playwright_post.py — note.com への投稿（Playwrightでブラウザ自動操作）

⚠️ これは「GitHub Actions などの“素の”実行環境」で動かす前提のスクリプトです。
   Claudeの実行環境（このリポジトリを生成しているクラウド）は、外向き通信が
   ポリシープロキシ経由に限定されており、ブラウザ（Chromium）が一切のHTTPSへ到達
   できないため、ここでは動きません。**投稿は GitHub Actions が担当**します
   （記事生成＝Claudeルーチン、投稿＝Actions、というXアカウント運用と同じ構成）。

やること:
  - NOTE_SESSION_COOKIE（長期有効な _note_session_v5 等）でログイン状態を復元
  - note のエディタ(/notes/new)を開き、タイトル・本文・アイキャッチを入力
  - QAが publish かつ PUBLISH_MODE=auto なら公開、それ以外は下書き保存
  - 各ステップのスクリーンショットを articles/<dir>/_debug/ に保存（Actionsのartifactで確認）
  - 例外は握って publish_result.json に記録（処理は止めるが原因が残る）

環境変数:
  NOTE_SESSION_COOKIE  必須（例: "_note_session_v5=xxxx" 。複数は "; " 区切り）
  NOTE_USERNAME        例: monoen_co_jp
  PUBLISH_MODE         auto（公開）| draft（下書きまで）  ※既定 draft（安全）
  DRY_RUN              1 なら公開ボタンを押さない（下書きで停止）
  ARTICLE_DIR          対象記事dir（未指定なら articles/ の最新日付dirを自動選択）
  HEADLESS             0 でヘッドフル（ローカルデバッグ用。既定 1）

注意:
  - これは非公式な自動化で、note の画面変更・bot対策で壊れ得ます（規約リスクも残ります）。
  - セレクタは note の実UIに合わせて“要調整”の箇所があります（# TUNE 参照）。
    初回は DRY_RUN=1 で実行し、_debug のスクショを見ながら詰めます。
"""
import json
import os
import re
import sys
import datetime as _dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW_NOTE_URL = "https://editor.note.com/new"   # note.com/notes/new はここへリダイレクトされる


def log(m): print(f"[note-pw] {m}", flush=True)


def clipurl(u): return (u or "")[:80]


# --------------------------------------------------------------------------- #
def pick_article_dir():
    d = os.getenv("ARTICLE_DIR")
    if d:
        return Path(d)
    cands = sorted([p for p in (ROOT / "articles").glob("20*-*") if (p / "metadata.json").exists()])
    if not cands:
        sys.exit("[note-pw] 対象記事が見つかりません")
    return cands[-1]


def md_to_plain_blocks(md: str):
    """Markdown本文を、noteへ入力する『ブロックのリスト』に変換（見出し/箇条書き/段落）。"""
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    blocks, buf = [], []

    def flush():
        if buf:
            blocks.append(("p", " ".join(buf).strip())); buf.clear()

    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            flush(); continue
        if s.startswith("### "):
            flush(); blocks.append(("h3", s[4:].strip()))
        elif s.startswith("## "):
            flush(); blocks.append(("h2", s[3:].strip()))
        elif re.match(r"^\s*[-*]\s+", s):
            flush(); blocks.append(("li", re.sub(r"^\s*[-*]\s+", "", s).strip()))
        elif re.match(r"^\s*\d+\.\s+", s):
            flush(); blocks.append(("li", re.sub(r"^\s*\d+\.\s+", "", s).strip()))
        else:
            buf.append(s.strip())
    flush()
    # 装飾記号を除去（**bold**, [text](url) → text（url））
    out = []
    for kind, t in blocks:
        t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
        t = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1（\2）", t)
        t = t.replace("`", "")
        out.append((kind, t))
    return out


# --------------------------------------------------------------------------- #
def run():
    from playwright.sync_api import sync_playwright

    d = pick_article_dir()
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    md = (d / "article.md").read_text(encoding="utf-8")
    qa = {}
    if (d / "qa.json").exists():
        qa = json.loads((d / "qa.json").read_text(encoding="utf-8"))
    title = meta.get("title") or md.splitlines()[0].lstrip("# ").strip()
    blocks = md_to_plain_blocks(md)
    eyecatch = d / "eyecatch.png"
    dbg = d / "_debug"; dbg.mkdir(exist_ok=True)

    mode = os.getenv("PUBLISH_MODE", "draft").lower()
    dry = os.getenv("DRY_RUN", "1") not in ("0", "false", "")
    want_publish = (mode == "auto" and qa.get("decision") != "draft" and not dry)

    cookie = os.getenv("NOTE_SESSION_COOKIE", "").strip()
    result = {"status": "unknown", "mode": mode, "dry_run": dry, "want_publish": want_publish,
              "note_url": "", "errors": [], "article_dir": str(d),
              "at": _dt.datetime.now().astimezone().isoformat(timespec="seconds")}

    def finish(status):
        result["status"] = status
        (d / "publish_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"RESULT: {status}  url={result['note_url'] or '-'}")
        sys.exit(0)

    if not cookie:
        result["errors"].append("NOTE_SESSION_COOKIE 未設定")
        finish("fallback_package")

    cookies = []
    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies.append({"name": k, "value": v, "domain": ".note.com", "path": "/"})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("HEADLESS", "1") != "0")
        ctx = browser.new_context(locale="ja-JP",
                                  viewport={"width": 1440, "height": 1000},
                                  user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        try:
            page.goto(NEW_NOTE_URL, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(6000)
            page.screenshot(path=str(dbg / "01_editor.png"), full_page=True)

            if "login" in page.url:
                result["errors"].append(f"ログイン状態が無効（{page.url}）。Cookie再取得が必要。")
                finish("fallback_package")

            # --- DOM probe（全フレームを走査。セレクタ調整用に結果JSONへ）---
            probe_js = r"""() => {
                const clip = s => (s||'').slice(0,70);
                const ph = [...document.querySelectorAll('input[placeholder],textarea[placeholder]')]
                    .map(e => ({tag:e.tagName, placeholder:clip(e.getAttribute('placeholder')), aria:clip(e.getAttribute('aria-label'))}));
                const ce = [...document.querySelectorAll('[contenteditable="true"],[contenteditable=""]')]
                    .map(e => ({tag:e.tagName, dph:clip(e.getAttribute('data-placeholder')), aria:clip(e.getAttribute('aria-label')), cls:clip(e.className)}));
                const tb = [...document.querySelectorAll('[role="textbox"]')]
                    .map(e => ({tag:e.tagName, aria:clip(e.getAttribute('aria-label')), dph:clip(e.getAttribute('data-placeholder'))}));
                const btn = [...document.querySelectorAll('button,[role="button"]')]
                    .map(e => clip((e.innerText||e.getAttribute('aria-label')||'').trim())).filter(Boolean).slice(0,50);
                return {placeholders:ph, contenteditables:ce, textboxes:tb, buttons:btn, bodyLen:document.body?document.body.innerText.length:0};
            }"""
            try:
                result["current_url"] = page.url
                frames = []
                for fr in page.frames:
                    try:
                        data = fr.evaluate(probe_js)
                    except Exception as fe:
                        data = {"error": str(fe)[:80]}
                    if any(data.get(k) for k in ("placeholders", "contenteditables", "textboxes", "buttons")):
                        frames.append({"frame_url": clipurl(fr.url), **data})
                result["frames_count"] = len(page.frames)
                result["editor_probe"] = frames or "全フレームで要素が見つかりません"
                # 何のページか診断（ローディング/ログイン/チャレンジ等の切り分け）
                result["page_title"] = page.title()
                result["page_text"] = page.evaluate("() => document.body ? document.body.innerText.slice(0,900) : ''")
                result["page_html_head"] = page.evaluate("() => document.body ? document.body.outerHTML.slice(0,1800) : ''")
            except Exception as e:
                result["errors"].append(f"probe失敗: {e}")

            if os.getenv("PROBE_ONLY", "0") == "1":
                finish("probe")

            # --- タイトル ---  # TUNE: placeholder文言はnoteのUIに合わせて調整
            title_box = page.get_by_placeholder(re.compile("記事タイトル|タイトル"))
            title_box.click(timeout=20000)
            page.keyboard.insert_text(title)
            page.wait_for_timeout(500)

            # --- 本文 ---  # TUNE: 本文エディタのlocator
            body = page.get_by_role("textbox").last
            body.click(timeout=20000)
            for i, (kind, text) in enumerate(blocks):
                page.keyboard.insert_text(text)
                page.keyboard.press("Enter")
                if i % 20 == 0:
                    page.wait_for_timeout(150)
            page.wait_for_timeout(800)
            page.screenshot(path=str(dbg / "02_body.png"))

            # --- アイキャッチ ---  # TUNE: 「画像を追加」→アップロード→保存 の導線
            if eyecatch.exists():
                try:
                    add_img = page.get_by_text(re.compile("画像を追加|見出し画像")).first
                    add_img.click(timeout=8000)
                    with page.expect_file_chooser(timeout=8000) as fc:
                        page.get_by_text(re.compile("アップロード|画像を選択")).first.click()
                    fc.value.set_files(str(eyecatch))
                    page.wait_for_timeout(2500)
                    save_btn = page.get_by_role("button", name=re.compile("保存|適用|決定|完了"))
                    if save_btn.count():
                        save_btn.first.click()
                    page.wait_for_timeout(1500)
                    page.screenshot(path=str(dbg / "03_eyecatch.png"))
                except Exception as e:
                    result["errors"].append(f"アイキャッチ設定失敗（本文のみ継続）: {e}")

            if not want_publish:
                # 下書き（noteは自動保存。明示保存があれば押す）
                try:
                    ds = page.get_by_role("button", name=re.compile("下書き保存|保存"))
                    if ds.count():
                        ds.first.click(); page.wait_for_timeout(1500)
                except Exception:
                    pass
                page.screenshot(path=str(dbg / "04_draft.png"))
                result["note_url"] = page.url
                finish("draft" if not dry else "dry_run_draft")

            # --- 公開 ---  # TUNE: 「公開に進む」→設定→「投稿する」
            page.get_by_role("button", name=re.compile("公開に進む|公開")).first.click(timeout=15000)
            page.wait_for_timeout(2000)
            # ハッシュタグ（任意）
            try:
                tagbox = page.get_by_placeholder(re.compile("ハッシュタグ|タグ"))
                if tagbox.count():
                    for h in meta.get("hashtags", [])[:5]:
                        tagbox.first.click(); page.keyboard.insert_text(h.lstrip("#"))
                        page.keyboard.press("Enter"); page.wait_for_timeout(300)
            except Exception:
                pass
            page.screenshot(path=str(dbg / "05_publish_settings.png"))
            page.get_by_role("button", name=re.compile("投稿する|公開する")).first.click(timeout=15000)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(dbg / "06_published.png"))
            result["note_url"] = page.url
            finish("published")

        except Exception as e:
            try:
                page.screenshot(path=str(dbg / "99_error.png"))
            except Exception:
                pass
            result["errors"].append(f"投稿中エラー: {e}")
            finish("fallback_package")
        finally:
            browser.close()


if __name__ == "__main__":
    run()
