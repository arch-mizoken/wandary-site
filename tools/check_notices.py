#!/usr/bin/env python3
"""content/announcements.json の見張り番。

お知らせはアプリの審査を通さずに届く。つまり、ここを壊すと
そのまま利用者の画面に出る。公開前に必ずこれを通す。

  python3 tools/check_notices.py                       確かめる
  python3 tools/check_notices.py --as 1.1.0            その版の人に何が出るか
  python3 tools/check_notices.py --as 1.1.0 --on 2026-10-15   その日に何が出るか
  python3 tools/check_notices.py --allow-stop          起動を止める配信を通す

この JSON は3つのものを運ぶ:

  announcements  ベルに入る「あとで読めばいいこと」
  notice         ホームの帯。「いま知る必要があること」を1件だけ
  appStatus      更新のうながし (帯 / 起動を止める)

決めごと:
  - お知らせは「出す日」の日付で出す。アプリのバッジ (ベルの赤い点) は
    利用者がその版を初めて起動した日以降のお知らせだけを数えるので、
    過去の日付で足すと、誰のベルにも点がつかない
  - version は中身を変えるたびに上げる。上げないと、すでに新しい版を
    受け取った端末が古い版を拾い直さない (アプリ側で弾いている)
  - 新機能の案内には minAppVersion を必ず書く。書かないと、
    まだ古い版の人に「◯◯ができます」が届く。開いても、無い
  - 1リリースにつき1件まで。ベルの点の値打ちを下げない
  - 帯 (notice) には publishUntil を必ず書く。消し忘れると常設の飾りになる
  - appStatus.minimumSupported は **起動を止める**。--allow-stop なしでは通らない
"""
import argparse, json, re, sys, datetime, pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "content" / "announcements.json"
LIMITS = {"title": 40, "body": 160}
DATE_KEYS = ("dateString", "publishFrom", "publishUntil")
VERSION_KEYS = ("minAppVersion", "maxAppVersion")
KNOWN = {"id", "emoji", "title", "body", "link"} | set(DATE_KEYS) | set(VERSION_KEYS)
KNOWN_TOP = {"version", "announcements", "notice", "appStatus"}
KNOWN_STATUS = {"recommended", "minimumSupported", "reason", "storeURL"}
VERSION_RE = r"\d+(\.\d+){1,2}"


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


def level(status, app_version):
    """アプリの AppStatus.level と同じ判定。強いほうが勝つ"""
    lo = status.get("minimumSupported")
    if lo and vtuple(app_version) < vtuple(lo):
        return "require"
    rec = status.get("recommended")
    if rec and vtuple(app_version) < vtuple(rec):
        return "recommend"
    return "none"


def check_item(a, where, iso, require_until=False):
    """お知らせ1件ぶん。帯 (notice) も同じ形なので同じ関所を通す"""
    errors, warnings = [], []

    for key in ("id", "dateString", "emoji", "title", "body"):
        if not a.get(key):
            errors.append(f"{where}: {key} がありません")

    for key in a:
        if key not in KNOWN:
            errors.append(f"{where}: 知らない項目 {key} (アプリは読み飛ばします)")

    for key in DATE_KEYS:
        raw = a.get(key)
        if raw and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            errors.append(f"{where}: {key} は YYYY-MM-DD で書きます ({raw})")
    for key in VERSION_KEYS:
        raw = a.get(key)
        if raw and not re.fullmatch(VERSION_RE, raw):
            errors.append(f"{where}: {key} は 1.2.0 の形で書きます ({raw})")

    if errors:
        return errors, warnings

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
    if require_until and not end:
        errors.append(
            f"{where}: 帯には publishUntil を書きます。"
            "消し忘れると、いつまでもホームの上に居座ります"
        )

    lo, hi = a.get("minAppVersion"), a.get("maxAppVersion")
    if lo and hi and vtuple(hi) < vtuple(lo):
        errors.append(f"{where}: maxAppVersion が minAppVersion より前です。誰にも出ません")

    for key, limit in LIMITS.items():
        if len(a.get(key, "")) > limit:
            warnings.append(f"{where}: {key} が{limit}文字を超えています ({len(a[key])}文字)")

    link = a.get("link")
    if link and not link.startswith("https://"):
        errors.append(f"{where}: link は https:// で始めます ({link})")

    return errors, warnings


def check_status(st, allow_stop):
    """更新のうながし。**ここだけは、通したくないほうが既定**"""
    errors, warnings = [], []
    where = "appStatus"

    if not isinstance(st, dict):
        return [f"{where}: 形が違います (辞書で書きます)"], warnings

    for key in st:
        if key not in KNOWN_STATUS:
            errors.append(f"{where}: 知らない項目 {key} (アプリは読み飛ばします)")

    for key in ("recommended", "minimumSupported"):
        raw = st.get(key)
        if raw and not re.fullmatch(VERSION_RE, raw):
            errors.append(f"{where}.{key} は 1.2.0 の形で書きます ({raw})")
    if errors:
        return errors, warnings

    rec, lo = st.get("recommended"), st.get("minimumSupported")

    if not rec and not lo:
        warnings.append(f"{where}: 何も書かれていません。誰にもうながしません")
    if (rec or lo) and not st.get("reason"):
        errors.append(
            f"{where}: reason を書きます。"
            "なぜ更新してほしいのかが無いと、ただの催促になります"
        )
    if st.get("reason") and len(st["reason"]) > 80:
        warnings.append(f"{where}.reason が80文字を超えています ({len(st['reason'])}文字)")
    if lo and rec and vtuple(lo) > vtuple(rec):
        errors.append(
            f"{where}: minimumSupported ({lo}) が recommended ({rec}) より新しいです。"
            "止めた人の行き先が、まだ出ていない版になります"
        )
    url = st.get("storeURL")
    if url and not url.startswith("https://"):
        errors.append(f"{where}.storeURL は https:// で始めます ({url})")

    if lo and not allow_stop:
        errors.append(
            f"{where}.minimumSupported が書かれています。"
            f"{lo} より古い人は**アプリを開いても止まります**。"
            "本当に出すなら --allow-stop を付けてください "
            "(使ってよい条件は petdiary/docs/10-お知らせの配信.md)"
        )
    return errors, warnings


def check(items, data, today, allow_stop=False):
    """today は datetime.date"""
    iso = today.isoformat()
    errors, warnings = [], []

    if not isinstance(data.get("version"), int) or data["version"] < 1:
        errors.append("version が整数ではありません")
    if not items:
        errors.append("お知らせが空です (アプリが空の配信を弾くので、届きません)")
    for key in data:
        if key not in KNOWN_TOP:
            errors.append(f"知らない項目 {key} (アプリは読み飛ばします)")

    seen = set()
    for i, a in enumerate(items):
        where = f"[{i}] {a.get('id', '(id なし)')}"
        if a.get("id") in seen:
            errors.append(f"{where}: id が重複しています")
        seen.add(a.get("id"))
        e, w = check_item(a, where, iso)
        errors += e
        warnings += w

    if "notice" in data and data["notice"] is not None:
        n = data["notice"]
        if not isinstance(n, dict):
            errors.append("notice: 形が違います (1件だけ、辞書で書きます)")
        else:
            e, w = check_item(n, f"notice {n.get('id', '(id なし)')}", iso, require_until=True)
            errors += e
            warnings += w
            if n.get("id") in seen:
                warnings.append(
                    "notice: ベルのお知らせと同じ id です。"
                    "同じことを2か所で言っています"
                )

    if "appStatus" in data and data["appStatus"] is not None:
        e, w = check_status(data["appStatus"], allow_stop)
        errors += e
        warnings += w

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
    ap.add_argument("--allow-stop", action="store_true",
                    help="起動を止める配信 (appStatus.minimumSupported) を通す")
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    items = data.get("announcements") or []

    errors, warnings = check(items, data, today, allow_stop=args.allow_stop)
    for w in warnings:
        print(f"注意: {w}")
    for e in errors:
        print(f"エラー: {e}")
    if errors:
        return 1

    if args.version:
        iso = today.isoformat()
        print(f"\n— {args.version} の人が {today} に見るもの —")
        shown = [a for a in items if visible(a, args.version, iso)]
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
                if a.get("publishFrom", "") > iso:
                    why.append(f"{a['publishFrom']} から")
                if a.get("publishUntil", "9999") < iso:
                    why.append(f"{a['publishUntil']} で終了")
                print(f"  – {a['title'][:24]}… : {' / '.join(why)}")
        if not shown:
            print("  (何も出ません)")

        n = data.get("notice")
        print("\n— ホームの帯 —")
        if n and visible(n, args.version, iso):
            print(f"  {n.get('emoji', '')} {n.get('title', '')}")
        else:
            print("  (出ません)")

        st = data.get("appStatus") or {}
        lv = level(st, args.version)
        print("\n— 更新のうながし —")
        print({"none": "  (出ません)",
               "recommend": f"  閉じられる帯: {st.get('reason', '')}",
               "require": f"  **起動を止めます**: {st.get('reason', '')}"}[lv])
        return 0

    extras = []
    if data.get("notice"):
        extras.append("帯1件")
    st = data.get("appStatus") or {}
    if st.get("minimumSupported"):
        extras.append(f"**起動を止める** ({st['minimumSupported']} 未満)")
    elif st.get("recommended"):
        extras.append(f"更新の帯 ({st['recommended']} 未満)")
    tail = " / " + " / ".join(extras) if extras else ""
    print(f"お知らせ {len(items)}件 / version {data['version']}{tail} — 問題ありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
