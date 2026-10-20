#!/usr/bin/env python3
"""配信する articles.json の形を見る。

    python3 tools/check_content.py                 # content/articles.json
    python3 tools/check_content.py <ファイル>      # 書き出す前の下書きでも

**なぜ要るのか**

記事を書いて Swift に入れて、書き出して、そこで長さの不備に気づく。
この往復を毎回やっていた。**書く段で止めれば、往復が消える。**

長さの範囲は、既存の記事から取っている。画面の行に収まる幅であって、
守らないと壊れるわけではない。ただ、そろっていないと見た目がばらつく。
"""
import json, pathlib, re, sys, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "content" / "articles.json"

TAGS = {"けんこう", "きせつ", "くらし"}
CATS = {"gohan", "unchi", "shi", "sanpo", "taichou", "kusuri", "shinsatsu", "memo"}
STAGES = {"puppy", "adult", "senior"}

TITLE = (10, 32)
LEAD = (21, 43)
PARA = (28, 110)
PARAS = (2, 3)

ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
OTHER_SCRIPT = re.compile(r"[Ѐ-ӿͰ-Ͽ]")
LATIN = re.compile(r"(?<![A-Za-z/.-])[A-Za-z]{2,}(?![A-Za-z/.-])")
ALLOW = {"kg", "ml", "kcal", "cm", "mm", "km", "pdf", "csv", "sns",
         "line", "ok", "ng", "wandary", "wbgt", "pm", "gw"}


def check(path):
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        print(f"読めません: {e}")
        return 1
    arts = data["articles"] if isinstance(data, dict) else data
    bad = []

    def ng(a, what):
        bad.append((a.get("id", "?"), what))

    seen = collections.Counter(a.get("id") for a in arts)
    for i, n in seen.items():
        if n > 1:
            bad.append((i, f"id が {n} 回出てくる"))

    for a in arts:
        for k in ("id", "emoji", "tag", "title", "lead", "paragraphs", "months"):
            if k not in a:
                ng(a, f"{k} がない")
        if "id" not in a:
            continue
        if not ID.match(a["id"]):
            ng(a, f"id の形: {a['id']}")
        if a.get("tag") not in TAGS:
            ng(a, f"tag: {a.get('tag')}")
        if not (TITLE[0] <= len(a.get("title", "")) <= TITLE[1]):
            ng(a, f"title {len(a.get('title',''))}字 (範囲 {TITLE[0]}〜{TITLE[1]})")
        if not (LEAD[0] <= len(a.get("lead", "")) <= LEAD[1]):
            ng(a, f"lead {len(a.get('lead',''))}字 (範囲 {LEAD[0]}〜{LEAD[1]})")
        ps = a.get("paragraphs") or []
        if not (PARAS[0] <= len(ps) <= PARAS[1]):
            ng(a, f"段落が {len(ps)}個 (範囲 {PARAS[0]}〜{PARAS[1]})")
        for n, p in enumerate(ps):
            if not (PARA[0] <= len(p) <= PARA[1]):
                ng(a, f"段落{n+1} が {len(p)}字 (範囲 {PARA[0]}〜{PARA[1]})")
        for m in a.get("months") or []:
            if not (1 <= m <= 12):
                ng(a, f"months: {m}")
        for s in a.get("ageStages") or []:
            if s not in STAGES:
                ng(a, f"ageStages: {s}")
        if a.get("relatedCategory") and a["relatedCategory"] not in CATS:
            ng(a, f"relatedCategory: {a['relatedCategory']}")
        # 書きかけの跡
        text = a.get("title", "") + a.get("lead", "") + "".join(ps)
        for m in OTHER_SCRIPT.finditer(text):
            ng(a, f"日本語でない文字: {m.group(0)}")
        for m in LATIN.finditer(text):
            if m.group(0).lower() not in ALLOW:
                ng(a, f"英単語が残っている: {m.group(0)}")
        if "【" in text:
            ng(a, "書きかけの印が残っている")

    if bad:
        print(f"{path.name}: {len(bad)} か所、直すところがあります\n")
        for i, what in bad:
            print(f"  {i:34s} {what}")
        return 1

    # 通ったときは、使える形で中身も出す
    print(f"{path.name}: {len(arts)} 本、形に問題はありません")
    per = collections.Counter()
    for a in arts:
        for m in a.get("months") or []:
            per[m] += 1
    def pool(stage, month):
        ok = [x for x in arts if not x.get("ageStages") or stage in x["ageStages"]]
        return sum(1 for x in ok if month in (x.get("months") or [])
                   or (x.get("ageStages") and stage in x["ageStages"]))
    print("\n「今週のおすすめ」が、まず選ぶ候補の数")
    print("              " + "".join(f"{m:3d}月" for m in range(1, 13)))
    for s, label in (("puppy", "子犬  "), ("adult", "成犬  "), ("senior", "シニア")):
        print(f"  {label}" + "".join(f"{pool(s, m):4d}" for m in range(1, 13)))
    free = sum(1 for a in arts if not (a.get("months") or [])
               and not a.get("ageStages") and not a.get("breeds"))
    print(f"\n縛りの無い棚 (毎週1本はここから): {free} 本")
    thin = sorted(range(1, 13), key=lambda m: pool("adult", m))[:3]
    print("いちばん薄い月:", "・".join(f"{m}月({pool('adult', m)}本)" for m in thin))
    return 0


if __name__ == "__main__":
    p = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    sys.exit(check(p))
