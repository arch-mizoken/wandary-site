#!/usr/bin/env python3
"""content/announcements.json の見張り番。

お知らせはアプリの審査を通さずに届く。つまり、ここを壊すと
そのまま利用者の画面に出る。公開前に必ずこれを通す。

  python3 tools/check_notices.py

決めごと:
  - お知らせは「出す日」の日付で出す。アプリのバッジ (ベルの赤い点) は
    利用者がその版を初めて起動した日以降のお知らせだけを数えるので、
    過去の日付で足すと、誰のベルにも点がつかない
  - version は中身を変えるたびに上げる。上げないと、すでに新しい版を
    受け取った端末が古い版を拾い直さない (アプリ側で弾いている)
  - 1リリースにつき1件まで。ベルの点の値打ちを下げない
"""
import json, re, sys, datetime, pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "content" / "announcements.json"
LIMITS = {"title": 40, "body": 160}


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    errors, warnings = [], []

    if not isinstance(data.get("version"), int) or data["version"] < 1:
        errors.append("version が整数ではありません")

    items = data.get("announcements") or []
    if not items:
        errors.append("お知らせが空です (アプリが空の配信を弾くので、届きません)")

    seen = set()
    today = datetime.date.today()
    for i, a in enumerate(items):
        where = f"[{i}] {a.get('id', '(id なし)')}"
        for key in ("id", "dateString", "emoji", "title", "body"):
            if not a.get(key):
                errors.append(f"{where}: {key} がありません")
        if a.get("id") in seen:
            errors.append(f"{where}: id が重複しています")
        seen.add(a.get("id"))

        raw = a.get("dateString", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            errors.append(f"{where}: dateString は YYYY-MM-DD で書きます ({raw})")
        else:
            d = datetime.date.fromisoformat(raw)
            if d > today:
                errors.append(f"{where}: 未来の日付です ({raw})")

        for key, limit in LIMITS.items():
            if len(a.get(key, "")) > limit:
                warnings.append(f"{where}: {key} が{limit}文字を超えています ({len(a[key])}文字)")

        link = a.get("link")
        if link and not link.startswith("https://"):
            errors.append(f"{where}: link は https:// で始めます ({link})")

    order = [a.get("dateString", "") for a in items]
    if order != sorted(order, reverse=True):
        warnings.append("新しい順に並んでいません (アプリ側で並べ替えるので表示は崩れません)")

    newest = max(order) if order else ""
    if newest and datetime.date.fromisoformat(newest) < today - datetime.timedelta(days=1):
        warnings.append(
            f"いちばん新しいお知らせが {newest} です。"
            "きょう公開するなら、その日付に直さないとベルに点がつきません"
        )

    for w in warnings:
        print(f"注意: {w}")
    for e in errors:
        print(f"エラー: {e}")
    if errors:
        return 1
    print(f"お知らせ {len(items)}件 / version {data['version']} — 問題ありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
