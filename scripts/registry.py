#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
registry.py — MONOEN note コンテンツ・レジストリのヘルパー（カニバリ制御）

役割:
  - keyword-map.yaml（計画）と content-registry.json（公開台帳）を読む
  - カニバリ（プライマリKWの共食い）を判定する
  - 次に書くべき候補スロットを、優先度×バランスで採点して提案する
    （トレンド点は、実行するClaudeセッションがWeb調査で付与し合算する）
  - 公開/保留の実績を台帳に追記する

CLI:
  python registry.py check "製造業 D2C" --intent how
  python registry.py suggest --top 8
  python registry.py distribution --days 14
  python registry.py add --file entry.json
  python registry.py list

依存: PyYAML
"""
import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYWORD_MAP = ROOT / "strategy" / "03-keyword-map.yaml"
REGISTRY = ROOT / "registry" / "content-registry.json"

PRIORITY_WEIGHT = {1: 4, 2: 3, 3: 2, 4: 1, 5: 0}


# --------------------------------------------------------------------------- #
# 読み込み / 保存
# --------------------------------------------------------------------------- #
def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML が必要です:  python3 -m pip install -r scripts/requirements.txt")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_keyword_map():
    return _load_yaml(KEYWORD_MAP)


def load_registry():
    with REGISTRY.open(encoding="utf-8") as f:
        return json.load(f)


def save_registry(data):
    with REGISTRY.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# --------------------------------------------------------------------------- #
# 正規化・類似
# --------------------------------------------------------------------------- #
def norm(s: str) -> str:
    """全半角/空白/記号のゆれを吸収して比較用に正規化。"""
    if s is None:
        return ""
    s = s.strip().lower()
    s = s.replace("　", " ")
    s = re.sub(r"[\s　]+", "", s)          # 空白除去
    s = re.sub(r"[／/｜|・,、。()（）\-—]", "", s)  # 区切り記号除去
    return s


def _tokens(s: str):
    return [t for t in re.split(r"[\s　／/｜|・,、]+", (s or "").strip()) if t]


def kw_overlap(a: str, b: str) -> float:
    """キーワードのトークン重なり率（0-1）。近接カニバリ検知の補助。"""
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# --------------------------------------------------------------------------- #
# 既存データの抽出
# --------------------------------------------------------------------------- #
def all_registered(reg):
    """published + held（保留）を返す。"""
    return list(reg.get("published", [])) + list(reg.get("held", []))


def published_kw_index(reg):
    """{norm(primary_kw): entry} を返す（published のみ）。"""
    idx = {}
    for e in reg.get("published", []):
        idx[norm(e.get("primary_kw", ""))] = e
    return idx


# --------------------------------------------------------------------------- #
# カニバリ判定
# --------------------------------------------------------------------------- #
def check_cannibalization(primary_kw: str, intent: str = None, reg=None, exclude_id: str = None):
    """
    戻り値: {
      "status": "ok" | "conflict" | "warn",
      "conflicts": [ {kw, intent, title, note_url, reason} ... ]
    }
    公開済み(published)＋下書き/保留(held)の両方を対象にする（下書き段階でも重複生成を防ぐ）。
    - 完全一致 → conflict（生成/公開停止レベル）
    - 高重なり(>=0.6) かつ 同一intent → conflict
    - 高重なり(>=0.6) かつ 異intent → warn（切り口が違えばOKだが要確認）
    exclude_id: 同一記事を下書き→公開へ昇格させる場合など、自分自身を除外するためのID。
    """
    if reg is None:
        reg = load_registry()
    n = norm(primary_kw)
    conflicts, warns = [], []
    for e in all_registered(reg):
        if exclude_id is not None and e.get("id") == exclude_id:
            continue
        en = norm(e.get("primary_kw", ""))
        ov = kw_overlap(primary_kw, e.get("primary_kw", ""))
        same_intent = intent is not None and e.get("intent") == intent
        st = e.get("status", "published")
        tag = "" if st == "published" else f"／{st}"
        if en == n:
            conflicts.append({**_slim(e), "reason": f"primary_kw 完全一致{tag}"})
        elif ov >= 0.6 and same_intent:
            conflicts.append({**_slim(e), "reason": f"KW重なり{ov:.0%}＋同一intent({intent}){tag}"})
        elif ov >= 0.6:
            warns.append({**_slim(e), "reason": f"KW重なり{ov:.0%}（intent違いで棲み分け要確認）{tag}"})
    if conflicts:
        return {"status": "conflict", "conflicts": conflicts, "warns": warns}
    if warns:
        return {"status": "warn", "conflicts": [], "warns": warns}
    return {"status": "ok", "conflicts": [], "warns": []}


def _slim(e):
    return {
        "id": e.get("id"),
        "primary_kw": e.get("primary_kw"),
        "intent": e.get("intent"),
        "title": e.get("title"),
        "note_url": e.get("note_url", ""),
    }


# --------------------------------------------------------------------------- #
# 配分・候補提案
# --------------------------------------------------------------------------- #
def recent_pillar_distribution(reg=None, days=14):
    if reg is None:
        reg = load_registry()
    cutoff = _dt.date.today() - _dt.timedelta(days=days)
    dist = {}
    for e in reg.get("published", []):
        try:
            d = _dt.date.fromisoformat(e.get("date", ""))
        except ValueError:
            continue
        if d >= cutoff:
            dist[e.get("pillar")] = dist.get(e.get("pillar"), 0) + 1
    return dist


def _pillar_has_pillar_page(reg, pillar_id):
    for e in reg.get("published", []):
        if e.get("pillar") == pillar_id and e.get("type") == "pillar":
            return True
    return False


def suggest_candidates(top=8, reg=None, kmap=None):
    """
    planned スロットを採点して上位を返す。
    score = priority_weight + primacy_bonus(ピラー未公開なら+3) + balance_bonus(直近で少ないピラー +2/+1)
            - trend_score はここでは 0。実行セッションがWeb調査で 0-3 を足す。
    カニバリ conflict のスロットは除外。
    """
    if reg is None:
        reg = load_registry()
    if kmap is None:
        kmap = load_keyword_map()
    dist = recent_pillar_distribution(reg, days=14)
    max_pub = max(dist.values()) if dist else 0
    published_ids = {e.get("id") for e in all_registered(reg)}

    rows = []
    for pillar in kmap.get("pillars", []):
        pid = pillar["id"]
        has_pillar = _pillar_has_pillar_page(reg, pid)
        for a in pillar.get("articles", []):
            if a.get("status") != "planned":
                continue
            if a.get("id") in published_ids:
                continue
            cann = check_cannibalization(a.get("primary_kw", ""), a.get("intent"), reg)
            if cann["status"] == "conflict":
                continue
            pr = a.get("priority", 3)
            score = PRIORITY_WEIGHT.get(pr, 1)
            primacy = 3 if (a.get("type") == "pillar" and not has_pillar) else 0
            # バランス: 直近で最も少ないピラーを底上げ（3連投抑制）
            pub = dist.get(pid, 0)
            if max_pub and pub == 0:
                balance = 2
            elif max_pub and pub < max_pub:
                balance = 1
            else:
                balance = 0
            score += primacy + balance
            rows.append({
                "id": a["id"], "pillar": pid, "type": a.get("type"),
                "primary_kw": a.get("primary_kw"), "intent": a.get("intent"),
                "title": a.get("title"), "priority": pr,
                "base_score": score, "primacy_bonus": primacy,
                "balance_bonus": balance,
                "note": "trend_score(0-3)を加算して最終決定",
                "cannibal_warn": cann.get("warns", []),
            })
    rows.sort(key=lambda r: (-r["base_score"], r["priority"]))
    return rows[:top]


# --------------------------------------------------------------------------- #
# 追記
# --------------------------------------------------------------------------- #
REQUIRED = ["id", "date", "title", "primary_kw", "intent", "pillar", "type", "status"]


def add_entry(entry: dict, reg=None):
    if reg is None:
        reg = load_registry()
    missing = [k for k in REQUIRED if not entry.get(k)]
    if missing:
        raise ValueError(f"必須フィールド不足: {missing}")
    # 公開扱いなら最終カニバリ確認（保険）。自分自身（同一id）の下書きは除外して昇格を許可。
    if entry["status"] == "published":
        cann = check_cannibalization(entry["primary_kw"], entry.get("intent"),
                                     reg, exclude_id=entry.get("id"))
        if cann["status"] == "conflict":
            raise ValueError(f"カニバリ conflict のため追記拒否: {cann['conflicts']}")
        # 同一idの下書きが held にあれば、公開昇格として held から取り除く
        reg["held"] = [h for h in reg.get("held", []) if h.get("id") != entry.get("id")]
        reg.setdefault("published", []).append(entry)
    else:  # draft / hold
        reg.setdefault("held", []).append(entry)
    reg.setdefault("meta", {})["updated"] = _dt.date.today().isoformat()
    save_registry(reg)
    return entry


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main():
    ap = argparse.ArgumentParser(description="MONOEN content registry helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="カニバリ判定")
    c.add_argument("primary_kw")
    c.add_argument("--intent", default=None)

    s = sub.add_parser("suggest", help="候補スロットを採点提案")
    s.add_argument("--top", type=int, default=8)

    d = sub.add_parser("distribution", help="直近のピラー配分")
    d.add_argument("--days", type=int, default=14)

    a = sub.add_parser("add", help="実績を追記")
    a.add_argument("--file", required=True, help="追記するJSONファイル")

    sub.add_parser("list", help="公開済み一覧")

    args = ap.parse_args()

    if args.cmd == "check":
        print(json.dumps(check_cannibalization(args.primary_kw, args.intent),
                         ensure_ascii=False, indent=2))
    elif args.cmd == "suggest":
        print(json.dumps(suggest_candidates(args.top), ensure_ascii=False, indent=2))
    elif args.cmd == "distribution":
        print(json.dumps(recent_pillar_distribution(days=args.days),
                         ensure_ascii=False, indent=2))
    elif args.cmd == "add":
        entry = json.loads(Path(args.file).read_text(encoding="utf-8"))
        print(json.dumps(add_entry(entry), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        reg = load_registry()
        for e in reg.get("published", []):
            print(f"{e.get('date')}  {e.get('id'):8}  {e.get('primary_kw')}  -> {e.get('note_url','')}")


if __name__ == "__main__":
    _main()
