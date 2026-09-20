#!/usr/bin/env python3
"""content/announcements.json の見張り番。

お知らせはアプリの審査を通さずに届く。つまり、ここを壊すと
そのまま利用者の画面に出る。公開前に必ずこれを通す。

  python3 tools/check_notices.py                       確かめる
  python3 tools/check_notices.py --as 1.1.0            その版の人に何が出るか
  python3 tools/check_notices.py --as 1.1.0 --on 2026-10-15   その日に何が出るか

決めごと:
  - お知らせは「出す日」の日付で出す。アプリのバッジ (ベルの赤い点) は
    利用者がその版を初めて起動した日以降のお知らせだけを数えるので、
    過去の日付で足すと、誰のベルにも点がつかない
  - version は中身を変えるたびに上げる。上げないと、すでに新しい版を
    受け取った端末が古い版を拾い直さない (アプリ側で弾いている)
  - 新機能の案内には minAppVersion を必ず書く。書かないと、
    まだ古い版の人に「◯◯ができます」が届く。開いても、無い
  - 1リリースにつき1件まで。ベルの点の値打ちを下げない
"""
import argparse, json, re, sys, datetime, pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "content" / "announcements.json"
LIMITS = {"title": 40, "body": 160}
DATE_KEYS = ("dateString", "publishFrom", "publishUntil")
VERSION_KEYS = ("minAppVersion", "maxAppVersion")
KNOWN = {"id", "emoji", "title", "body", "link"} | set(DATE_KEYS) | set(VERSION_KEYS)


def vtuple(v):
    return tuple(int(x) for x in v.split("."))


def visible(a, app_version, today):
    """アプリの Announcement.isVisible と同じ判定。片方だけ直すと意味がない"""
    if a.get("publishFrom") and today < a["publishFrom"]:
        return False
    if a.get("publishUntil") and today > a["publishUntil"]:
        return False
    if a.get("minAppVersion") and vtuple(app_version) < vtuple(a["minAppVersion"]):
        return False
    if a.get("maxAppVersion") and vtuple(app_version) > vtuple(a["maxAppVersion"]):
        return False
    return True


def check(items, data, today):
    """today は datetime.date"""
    iso = today.isoformat()
    errors, warnings = [], []

    if not isinstance(data.get("version"), int) or data["version"] < 1:
        errors.append("version が整数ではありません")
    if not items:
        errors.append("お知らせが空です (アプリが空の配信を弾くので、届きません)")

    seen = set()
    for i, a in enumerate(items):
        where = f"[{i}] {a.get('id', '(id なし)')}"
        for key in ("id", "dateString", "emoji", "title", "body"):
            if not a.get(key):
                errors.append(f"{where}: {key} がありません")
        if a.get("id") in seen:
            errors.append(f"{where}: id が重複しています")
        seen.add(a.get("id"))

        for key in a:
            if key not in KNOWN:
                errors.append(f"{where}: 知らない項目 {key} (アプリは読み飛ばします)")

        for key in DATE_KEYS:
            raw = a.get(key)
            if raw and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                errors.append(f"{where}: {key} は YYYY-MM-DD で書きます ({raw})")
        for key in VERSION_KEYS:
            raw = a.get(key)
            if raw and not re.fullmatch(r"\d+(\.\d+){1,2}", raw):
                errors.append(f"{where}: {key} は 1.2.0 の形で書きます ({raw})")

        if errors:
            continue

        start = a.get("publishFrom")
        end = a.get("publishUntil")
        if start and end and end < start:
            errors.append(f"{where}: publishUntil が publishFrom より前です")
        if start and a["dateString"] != start:
            warnings.append(
                f"{where}: 予約公開の日付と表示の日付が違います "
                f"(出るのは {start}、画面に出る日付は {a['dateString']})"
            )
        if not start and a["dateString"] > iso:
            errors.append(
                f"{where}: 未来の日付です ({a['dateString']})。"
                "先の日に出すなら publishFrom を書きます"
            )
        if end and end < iso:
            warnings.append(f"{where}: 公開期間が終わっています ({end})。消してよいはずです")

        lo, hi = a.get("minAppVersion"), a.get("maxAppVersion")
        if lo and hi and vtuple(hi) < vtuple(lo):
            errors.append(f"{where}: maxAppVersion が minAppVersion より前です。誰にも出ません")

        for key, limit in LIMITS.items():
            if len(a.get(key, "")) > limit:
                warnings.append(f"{where}: {key} が{limit}文字を超えています ({len(a[key])}文字)")

        link = a.get("link")
        if link and not link.startswith("https://"):
            errors.append(f"{where}: link は https:// で始めます ({link})")

    order = [a.get("dateString", "") for a in items]
    if order != sorted(order, reverse=True):
        warnings.append("新しい順に並んでいません (アプリ側で並べ替えるので表示は崩れません)")

    live = [a for a in items if not a.get("publishFrom", "") > iso]
    newest = max((a["dateString"] for a in live), default="")
    if newest and newest < (today - datetime.timedelta(days=1)).isoformat():
        warnings.append(
            f"いちばん新しいお知らせが {newest} です。"
            "きょう公開するなら、その日付に直さないとベルに点がつきません"
        )
    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as", dest="version", help="この版の人として見る (例: 1.1.0)")
    ap.add_argument("--on", dest="date", help="この日として見る (例: 2026-10-15)")
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    items = data.get("announcements") or []

    errors, warnings = check(items, data, today)
    for w in warnings:
        print(f"注意: {w}")
    for e in errors:
        print(f"エラー: {e}")
    if errors:
        return 1

    if args.version:
        print(f"\n— {args.version} の人が {today} に見るもの —")
        shown = [a for a in items if visible(a, args.version, today.isoformat())]
        for a in shown:
            print(f"  {a['emoji']} {a['title']}  ({a['dateString']})")
        for a in items:
            if a not in shown:
                why = []
                if a.get("minAppVersion") and vtuple(args.version) < vtuple(a["minAppVersion"]):
                    print(f"  – {a['title'][:24]}… : {a['minAppVersion']} 以上の人にだけ")
                    continue
                if a.get("maxAppVersion") and vtuple(args.version) > vtuple(a["maxAppVersion"]):
                    print(f"  – {a['title'][:24]}… : {a['maxAppVersion']} 以下の人にだけ")
                    continue
                if a.get("publishFrom", "") > today.isoformat():
                    why.append(f"{a['publishFrom']} から")
                if a.get("publishUntil", "9999") < today.isoformat():
                    why.append(f"{a['publishUntil']} で終了")
                print(f"  – {a['title'][:24]}… : {' / '.join(why)}")
        if not shown:
            print("  (何も出ません)")
        return 0

    print(f"お知らせ {len(items)}件 / version {data['version']} — 問題ありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
