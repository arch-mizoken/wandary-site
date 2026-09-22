#!/usr/bin/env python3
"""_goods/*.md から、アプリが取りにいく content/picks.json を作る。

    python3 tools/build_picks.py
    python3 tools/build_picks.py --check    ← 書き出さず、ずれているかだけ見る

**なぜ要るか**

アプリの「編集部の道具箱」(ReadingView) と月刊誌の巻末は、この picks.json を
読んで出している。ところが作る道具が無く、**中身が空のまま公開されていた。**

    content/picks.json → {"version": 1, "picks": []}

空だと `if !toolbox.isEmpty` でセクションごと消えるので、画面は壊れて見えない。
**気づけないまま、記事5本に誰も来ない。**articles.json とまったく同じ壊れ方で、
あちらは scripts/export-content.sh で塞いだ。こちらがその対になる。

**petdiary 側にも同名の tools/build_picks.py がある。**あれは xlsx を入力にして
picks.json と goods/*.html の両方を書くので、走らせると**このサイトの記事5本を
スタブで上書きする。**使わないこと (向こうにも止め板を入れてある)。

記事の前書きに、アプリ用の項目を足してある:

    emoji:    アプリの一覧に出る絵文字 (必須)
    pickcat:  アプリの表示分類 たべる / おでかけ / おうち / ケア (必須)
    ages:     全世代 | 子犬, 成犬, シニア犬 (任意)
    breeds:   犬種。プロフィールの犬種と部分一致で当てる (任意)
    months:   1〜12。季節ものだけ。空なら通年 (任意)
    pick1..3: アプリ内に出す編集部のコメント。**記事本文を丸ごと入れない。**
              アプリで読ませるのは要点まで、続きはサイトで読んでもらう
    picknot:  「合わなかったところ」の要約 (任意)

**pick1..3 に、記事に書いていない体験を書かないこと。**縮めるのはいいが、
足すのは景表法の問題になる。
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_goods import parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_goods"
OUT = ROOT / "content" / "picks.json"

CATEGORIES = {"たべる", "おでかけ", "おうち", "ケア"}
ALL_STAGES = ["puppy", "adult", "senior"]
STAGE_MAP = {"子犬": "puppy", "成犬": "adult", "シニア犬": "senior"}
# 3世代すべて = 「どの子に出してもよい」。空欄との違いは、アプリ側が
# 明示だと判定できること (Pick.coversAllStages)
ALL_LABEL = "全世代"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def split_list(s):
    return [p.strip() for p in re.split(r"[,、]", s or "") if p.strip()]


def build():
    picks, problems = [], []
    for path in sorted(SRC.glob("*.md")):
        meta = parse(path)
        if meta.get("draft", "").lower() == "true":
            continue
        slug = meta["slug"]

        def bad(msg):
            problems.append(f"  {path.name}: {msg}")

        if not ID_RE.match(slug):
            bad("ファイル名は英小文字・数字・ハイフンだけにしてください")
            continue
        if not (ROOT / "goods" / f"{slug}.html").exists():
            bad(f"goods/{slug}.html がありません。先に build_goods.py を走らせてください")
            continue

        emoji, cat = meta.get("emoji", ""), meta.get("pickcat", "")
        if not emoji:
            bad("emoji がありません")
        if cat not in CATEGORIES:
            bad(f"pickcat「{cat}」は {' / '.join(sorted(CATEGORIES))} のどれかにしてください")

        comment = [meta[k].strip() for k in ("pick1", "pick2", "pick3")
                   if meta.get(k, "").strip()]
        if not comment:
            bad("pick1 がありません (アプリに出すコメント)")

        labels = split_list(meta.get("ages", ""))
        stages = []
        if labels == [ALL_LABEL]:
            stages = list(ALL_STAGES)
        elif ALL_LABEL in labels:
            bad(f"ages は「{ALL_LABEL}」だけか、世代の組み合わせかのどちらかにしてください")
        else:
            for l in labels:
                if l not in STAGE_MAP:
                    bad(f"ages「{l}」は {ALL_LABEL} / 子犬 / 成犬 / シニア犬 のどれかに")
                else:
                    stages.append(STAGE_MAP[l])

        months = []
        for m in split_list(meta.get("months", "")):
            if not m.isdigit() or not 1 <= int(m) <= 12:
                bad(f"months「{m}」は 1〜12 の数字にしてください")
            else:
                months.append(int(m))

        pick = {
            "id": slug,
            "emoji": emoji,
            "category": cat,
            "title": meta["title"],
            "lead": meta["lead"],
            "comment": comment,
            "notRecommended": meta.get("picknot", "").strip() or None,
            # PickEndpoints.goodsBase (= /goods/) からの相対
            "linkPath": f"{slug}.html",
            "months": sorted(set(months)),
        }
        if stages:
            pick["ageStages"] = sorted(set(stages), key=ALL_STAGES.index)
        if meta.get("breeds"):
            pick["breeds"] = split_list(meta["breeds"])
        if meta.get("keywords"):
            pick["keywords"] = split_list(meta["keywords"])
        picks.append(pick)
    return picks, problems


def main():
    check = "--check" in sys.argv
    picks, problems = build()
    if problems:
        print("直してください:")
        print("\n".join(problems))
        return 1

    old = {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
    # 版は「前より大きい」ことだけが要る (端末のキャッシュを追い越すため)
    version = old.get("version", 0) + 1 if old.get("picks") != picks else old.get("version", 1)
    body = {"version": version, "picks": picks}

    if check:
        if old.get("picks") == picks:
            print(f"同梱と配信は同じです ({len(picks)}件)")
            return 0
        print(f"ずれています — 記事 {len(picks)}件 / 配信 {len(old.get('picks', []))}件")
        print("そろえるには: python3 tools/build_picks.py")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(picks)}件を書き出しました (version {version}): {OUT}")
    for p in picks:
        stages = "/".join(p.get("ageStages", [])) or "指定なし"
        print(f"  {p['emoji']} {p['id']:<20} {p['category']}  {stages}")
    print()
    print("このあと: git add -A && git commit && git push")
    print("アプリは picks.json を自動で取りにいくので、審査は要りません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
