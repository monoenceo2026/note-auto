#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
note_publisher.py — note.com への投稿（非公式API・完全自動公開/下書き）

⚠️ 重要な前提
  - note には「公式の投稿API」がありません。本スクリプトは、ログイン済みブラウザの
    セッションCookieを使う「非公式」な方法です。note の仕様変更で動かなくなること、
    利用規約上のリスクがあることを理解の上で使ってください（SETUP.md / OPERATIONS.md）。
  - エンドポイントやレスポンス形式は予告なく変わり得ます。動かない場合は下の ENDPOINTS を
    ブラウザの開発者ツール(Network)で確認して更新してください。

設計の安全性
  - DRY_RUN=1（既定）では実際のAPIを叩かず、送信内容だけログ出力します。
  - どんな失敗でも例外で日次処理を止めず、必ず publish_result.json を書きます。
  - 失敗時は status="fallback_package" とし、ローカルの完成パッケージを手動投稿できるようにします。
  - QAが decision="draft" の記事は、PUBLISH_MODE=auto でも絶対に publish しません（下書き止まり）。

使い方:
  python3 note_publisher.py --dir articles/2026-07-19-xxx
  python3 note_publisher.py --dir articles/... --whoami   # Cookieの有効性を軽くチェック

入力（--dir 内）:
  article.md, metadata.json, qa.json（任意）, eyecatch.png（任意）
出力:
  --dir/note_body.html, --dir/publish_result.json
"""
import argparse
import json
import os
import sys
import datetime as _dt
from pathlib import Path

BASE = "https://note.com"

# ---- 非公式エンドポイント（動かない場合はここを更新）-----------------------
ENDPOINTS = {
    "bootstrap":    f"{BASE}/",                                   # XSRF-TOKEN cookie取得用
    "upload_image": f"{BASE}/api/v1/upload_image",               # POST multipart 'file'
    "create_note":  f"{BASE}/api/v1/text_notes",                 # POST {name, body} -> id/key
    "save_draft":   f"{BASE}/api/v1/text_notes/draft_save",      # POST ?id=..&is_temp_saved=true
    "publish":      f"{BASE}/api/v2/notes/{{key}}/publish",      # POST 公開
}


def _load_env():
    try:
        from dotenv import load_dotenv
        env = Path(__file__).resolve().parent / ".env"
        if env.exists():
            load_dotenv(env)
    except Exception:
        pass


def log(msg):
    print(f"[note] {msg}")


# --------------------------------------------------------------------------- #
# Markdown -> note向けHTML
# --------------------------------------------------------------------------- #
def md_to_note_html(md_text: str) -> str:
    """
    note本文向けにMarkdownをHTML化。noteが解釈しやすい素朴なHTMLに寄せる。
    1行目の `# タイトル` はタイトル扱いなので本文からは除外する。
    """
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body_md = "\n".join(lines).strip()

    try:
        from markdown_it import MarkdownIt
        html = MarkdownIt("commonmark", {"html": False, "linkify": True}) \
            .enable("table").render(body_md)
    except Exception:
        html = _fallback_md(body_md)

    # 使えるタグに絞る（あれば）
    try:
        from bs4 import BeautifulSoup
        allowed = {"h2", "h3", "h4", "p", "ul", "ol", "li", "a", "strong", "em",
                   "blockquote", "br", "table", "thead", "tbody", "tr", "th", "td", "hr"}
        soup = BeautifulSoup(html, "html.parser")
        # h1 は h2 に降格（note本文にh1は不要）
        for h1 in soup.find_all("h1"):
            h1.name = "h2"
        for tag in soup.find_all(True):
            if tag.name not in allowed:
                tag.unwrap()
        html = str(soup)
    except Exception:
        pass
    return html


def _fallback_md(md_text: str) -> str:
    """markdown-it が無い場合の最小変換。"""
    import re
    out = []
    for para in md_text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        if p.startswith("### "):
            out.append(f"<h3>{p[4:].strip()}</h3>")
        elif p.startswith("## "):
            out.append(f"<h2>{p[3:].strip()}</h2>")
        elif all(l.lstrip().startswith(("- ", "* ")) for l in p.splitlines()):
            items = "".join(f"<li>{l.lstrip()[2:].strip()}</li>" for l in p.splitlines())
            out.append(f"<ul>{items}</ul>")
        else:
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', p)
            out.append(f"<p>{p}</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# note セッション
# --------------------------------------------------------------------------- #
def build_session(cookie_str: str):
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": BASE,
        "Referer": BASE + "/",
    })
    # Cookie文字列を分解して投入
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            s.cookies.set(k, v, domain="note.com")
    return s


def ensure_xsrf(session):
    """note.com を一度GETして XSRF-TOKEN cookie を得て、ヘッダに設定。"""
    try:
        session.get(ENDPOINTS["bootstrap"], timeout=20)
        token = session.cookies.get("XSRF-TOKEN")
        if token:
            import urllib.parse
            session.headers["X-XSRF-TOKEN"] = urllib.parse.unquote(token)
            return True
    except Exception as e:
        log(f"XSRF取得に失敗（続行はするが公開失敗の可能性）: {e}")
    return False


def whoami(session):
    """Cookieの有効性を軽く確認（読み取り系）。確証ではないが早期検知に有効。"""
    import requests
    for url in (f"{BASE}/api/v2/notes?kind=note&page=1", f"{BASE}/api/v1/stats/pv?filter=all&page=1"):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                return True, url
        except requests.RequestException:
            continue
    return False, None


# --------------------------------------------------------------------------- #
# 投稿フロー
# --------------------------------------------------------------------------- #
def upload_image(session, image_path: Path):
    with image_path.open("rb") as f:
        files = {"file": (image_path.name, f, "image/png")}
        r = session.post(ENDPOINTS["upload_image"], files=files, timeout=60)
    r.raise_for_status()
    data = r.json()
    # レスポンス形の揺れに対応
    for k in ("url", "key", "image_key"):
        d = data.get("data", data)
        if isinstance(d, dict) and d.get(k):
            return d[k]
    return json.dumps(data)[:200]


def create_note(session, title, body_html):
    r = session.post(ENDPOINTS["create_note"], json={"name": title, "body": body_html}, timeout=60)
    r.raise_for_status()
    data = r.json().get("data", r.json())
    return data.get("id"), data.get("key")


def save_draft(session, note_id, title, body_html):
    params = {"id": note_id, "is_temp_saved": "true"}
    payload = {
        "name": title, "body": body_html,
        "body_length": len(body_html), "index": False, "is_lead_form": False,
    }
    r = session.post(ENDPOINTS["save_draft"], params=params, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def publish_note(session, key, hashtags=None, eyecatch_key=None):
    payload = {}
    if hashtags:
        payload["hashtags"] = [{"hashtag": {"name": h.lstrip("#")}} for h in hashtags]
    if eyecatch_key:
        payload["eyecatch"] = eyecatch_key
    r = session.post(ENDPOINTS["publish"].format(key=key), json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- #
# メイン
# --------------------------------------------------------------------------- #
def main():
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="記事ディレクトリ")
    ap.add_argument("--whoami", action="store_true", help="Cookie有効性チェックのみ")
    args = ap.parse_args()

    d = Path(args.dir)
    result = {
        "status": "unknown", "mode": None, "dry_run": None,
        "note_url": "", "note_key": "", "errors": [],
        "at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    def finish(status, code=0):
        result["status"] = status
        (d / "publish_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"RESULT: {status}  note_url={result['note_url'] or '-'}")
        sys.exit(code)

    # --- 入力読み込み ---
    try:
        md = (d / "article.md").read_text(encoding="utf-8")
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    except Exception as e:
        result["errors"].append(f"入力読み込み失敗: {e}")
        finish("error", 0)

    qa = {}
    if (d / "qa.json").exists():
        try:
            qa = json.loads((d / "qa.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    title = meta.get("title") or (md.splitlines()[0].lstrip("# ").strip() if md else "無題")
    body_html = md_to_note_html(md)
    (d / "note_body.html").write_text(body_html, encoding="utf-8")

    mode = os.getenv("PUBLISH_MODE", "package").lower()      # auto|draft|package
    dry = os.getenv("DRY_RUN", "1") not in ("0", "false", "False", "")
    result["mode"], result["dry_run"] = mode, dry

    # QAが draft指定なら、autoでも公開しない
    qa_decision = qa.get("decision")
    effective_publish = (mode == "auto" and qa_decision != "draft")
    if mode == "auto" and qa_decision == "draft":
        result["errors"].append("QA decision=draft のため公開せず下書き止まりにダウングレード")

    # --- package モード：noteに触れない ---
    if mode == "package":
        log("PUBLISH_MODE=package: noteへは投稿しません。ローカルパッケージのみ。")
        finish("package_only", 0)

    cookie = os.getenv("NOTE_SESSION_COOKIE", "").strip()
    if not cookie:
        result["errors"].append("NOTE_SESSION_COOKIE 未設定。手動投稿用にパッケージのみ残します。")
        finish("fallback_package", 0)

    # --- DRY_RUN：送信内容だけ確認 ---
    if dry:
        log("DRY_RUN=1: 実APIは呼びません。以下を送信予定でした。")
        log(f"  title={title!r}")
        log(f"  body_html={len(body_html)} chars")
        log(f"  hashtags={meta.get('hashtags')}")
        log(f"  eyecatch={'あり' if (d/'eyecatch.png').exists() else 'なし'}")
        log(f"  effective action = {'PUBLISH' if effective_publish else 'DRAFT'}")
        result["note_url"] = "(dry-run: not created)"
        finish("dry_run_ok", 0)

    # --- 実投稿（例外は必ず捕捉してfallback）---
    try:
        session = build_session(cookie)
        ensure_xsrf(session)

        if args.whoami:
            ok, url = whoami(session)
            result["errors"].append(f"whoami: {'OK' if ok else 'NG'} ({url})")
            finish("whoami_ok" if ok else "whoami_ng", 0)

        ok, _ = whoami(session)
        if not ok:
            result["errors"].append("Cookie無効の可能性（whoami失敗）。fallbackします。")
            finish("fallback_package", 0)

        eyecatch_key = None
        if (d / "eyecatch.png").exists():
            try:
                eyecatch_key = upload_image(session, d / "eyecatch.png")
                log(f"eyecatch uploaded: {str(eyecatch_key)[:60]}")
            except Exception as e:
                result["errors"].append(f"アイキャッチ投稿失敗（画像なしで継続）: {e}")

        note_id, key = create_note(session, title, body_html)
        result["note_key"] = key or ""
        save_draft(session, note_id, title, body_html)
        log(f"draft saved: id={note_id} key={key}")

        if effective_publish:
            pub = publish_note(session, key, meta.get("hashtags"), eyecatch_key)
            url = ""
            if isinstance(pub, dict):
                data = pub.get("data", pub)
                url = data.get("note_url") or data.get("url") or ""
            uname = os.getenv("NOTE_USERNAME", "").strip()
            if not url and key and uname:
                url = f"{BASE}/{uname}/n/{key}"
            result["note_url"] = url
            finish("published", 0)
        else:
            result["note_url"] = f"{BASE}/notes/{key}/edit" if key else ""
            finish("draft", 0)

    except Exception as e:
        result["errors"].append(f"投稿中エラー: {e}")
        finish("fallback_package", 0)


if __name__ == "__main__":
    main()
