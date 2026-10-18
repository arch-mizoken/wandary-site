#!/usr/bin/env python3
"""体験の枠が空いている記事を、公開が近い順に並べる。

    python3 tools/holes.py           # 画面に出す
    python3 tools/holes.py --fill    # 書き込む用のファイルを作る

本文に `【要記入：…】` が残っているあいだ、その記事は日が来ても公開されない
(build_articles.py が止める)。ここはその一覧。

**全部に答える必要はない。**公開日が近いものから埋めれば、間に合う。
"""
import pathlib, re, sys, datetime, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_articles"
OUT = ROOT / "_drafts" / "体験の宿題.md"


def holes():
    found = []
    for p in sorted(SRC.glob("*.md")):
        t = p.read_text()
        m = re.search(r"【要記入：(.+?)】", t, re.S)
        if not m:
            continue
        meta = {k: re.search(rf"^{k}: (.+)$", t, re.M).group(1)
                for k in ("cat", "date", "title")}
        found.append({**meta, "slug": p.stem,
                      "q": " ".join(m.group(1).split())})
    found.sort(key=lambda x: (x["date"], x["slug"]))
    return found


def main():
    rows = holes()
    today = datetime.date.today()
    by_month = collections.Counter(r["date"][:7] for r in rows)

    if "--fill" not in sys.argv:
        print(f"体験の枠が空いている記事: {len(rows)} 本\n")
        print("公開月ごと:")
        for month, n in sorted(by_month.items()):
            soon = "  ← 近い" if month <= (today + datetime.timedelta(days=45)).isoformat()[:7] else ""
            print(f"  {month}  {n:3d}本{soon}")
        print("\n公開が近い10本:\n")
        for r in rows[:10]:
            left = (datetime.date.fromisoformat(r["date"]) - today).days
            print(f"  {r['date']} (あと{left}日)  {r['title']}")
            print(f"      {r['q']}\n")
        print("書き込む用のファイルを作るには: python3 tools/holes.py --fill")
        return 0

    lines = [
        "# 体験の宿題",
        "",
        f"**{len(rows)}本。**公開が近い順に並べてあります。",
        "",
        "**全部に答える必要はありません。**日付が近いものから埋めれば間に合います。",
        "各質問の下の空行に、一言でいいので書いてください。",
        "長さは問いません。**書けない回は飛ばして構いません**（その記事は公開されないだけです）。",
        "",
        "このファイルは `_drafts/` にあるので、公開されません。",
        "",
    ]
    cur = ""
    for r in rows:
        if r["date"][:7] != cur:
            cur = r["date"][:7]
            lines += ["", f"## {cur}（{by_month[cur]}本）", ""]
        left = (datetime.date.fromisoformat(r["date"]) - today).days
        lines += [
            f"### {r['date']}（あと{left}日） {r['title']}",
            f"`{r['slug']}` ・ {r['cat']}",
            "",
            f"> {r['q']}",
            "",
            "**→ **",
            "",
        ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT.relative_to(ROOT)} に {len(rows)} 本ぶん書きました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
