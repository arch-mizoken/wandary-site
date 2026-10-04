#!/usr/bin/env python3
"""公開しているHTMLの内部リンクを全部たどって、行き先があるか確かめる。

    python3 tools/check_links.py

**なぜ要るか**: よみものは公開日を予約して出している。まだ公開されていない
記事へリンクを貼ると、その日まで404になる。書いているときは原稿が
`_articles/` にあるので、こちらは「ある」と思い込んでしまう。

実際に 2026-09-21、道具箱の2本から、公開日が1か月先の記事へリンクしていた。
気づいたのは読者ではなく偶然で、それでは遅い。**ビルドのたびに機械で見る。**

外部リンク (https://) は見ない。アフィリエイトのリンクを叩くことになるため。
"""
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# nyandary は開発中の別サイト (いずれ別ドメインへ移す)。
# wandary.jp のページではないので、ここでは見ない
SKIP_DIRS = {"_articles", "_goods", "_drafts", "tools", ".git", "nyandary"}

def targets(href):
    """そのURLが、どのファイルに当たるか"""
    path = href.split("#")[0].split("?")[0]
    if not path or path == "/":
        return ROOT / "index.html"
    if path.endswith("/"):
        return ROOT / (path.lstrip("/") + "index.html")
    return ROOT / path.lstrip("/")

# 制度の金額や期限は変わる。**変わったことに気づかないのが、いちばん怖い。**
# 実際、マイクロチップの登録手数料は2024年4月に上がっていたのに、
# 2026年9月まで古い金額 (300円/1,000円) を載せたままだった。
#
# 出典と、最後に確かめた日を持つ。古くなったら、ここが言う。
FACTS = [
    # (何の数字か, 公開しているページに出ているべき語, 最後に確かめた日, 出典)
    ("マイクロチップ登録手数料", "400円", "2026-09-22",
     "https://www.env.go.jp/nature/dobutsu/aigo/pickup/chip.html"),
    ("犬の登録手数料", "3,000円", "2026-09-22",
     "https://www.mhlw.go.jp/bunya/kenkou/kekkaku-kansenshou10/10.html"),
    ("注射済票の交付手数料", "550円", "2026-09-22",
     "https://www.mhlw.go.jp/bunya/kenkou/kekkaku-kansenshou10/10.html"),
]
STALE_AFTER_DAYS = 365


def check_facts():
    """載せている金額が、確かめた日から1年たっていないか"""
    import datetime
    today = datetime.date.today()
    old = []
    for name, _, checked, src in FACTS:
        days = (today - datetime.date.fromisoformat(checked)).days
        if days > STALE_AFTER_DAYS:
            old.append(f"  {name} — {days}日前に確かめたきり  {src}")
    if old:
        print("確かめ直したほうがいい数字:")
        print("\n".join(old))
        print()
    return len(old)


def check_scripts(pages):
    """ページが読むべき script を、読んでいるか。

    `goods/track.js` は、商品ページに data-outbound を置いたのに
    **どこからも読み込まれていなかった。**計測が動いていないことは、
    画面を見ても分からない。だから機械に見張らせる。
    """
    bad = []
    for page in pages:
        s = page.read_text(encoding="utf-8")
        if '<meta name="robots" content="noindex' in s:
            continue
        if 'src="/ga.js"' not in s:
            bad.append((page, "/ga.js"))
        if "data-outbound" in s and 'src="/goods/track.js"' not in s:
            bad.append((page, "/goods/track.js"))
    if bad:
        print("読み込まれていない script があります:")
        for page, src in bad:
            print(f"  {page.relative_to(ROOT)}  ←  {src}")
        print()
    return len(bad)


def check_ga_and_policy():
    """計測していることと、公表していることが、合っているか。

    片方だけになっているのが、いちばんまずい:
    - ID は入っているが、ポリシーに書いていない → 公表していない送信
    - ポリシーには書いてあるが、ID が空 → 使っていないものを使うと書いている

    `tools/enable_ga.py` が両方を同時に書き換えるので、ふつうはずれない。
    手で片方だけ触ったときに、ここで止まる
    """
    ga = (ROOT / "ga.js").read_text()
    measuring = bool(re.search(r"^var WANDARY_GA = '(G-[^']+)';", ga, re.M))
    disclosed = "Google アナリティクス" in (ROOT / "privacy.html").read_text()
    if measuring == disclosed:
        return 0
    if measuring:
        print("ga.js に測定IDが入っていますが、プライバシーポリシーに書いてありません。")
    else:
        print("プライバシーポリシーに Google アナリティクスと書いてありますが、"
              "ga.js の測定IDが空です。")
    print("  python3 tools/enable_ga.py G-XXXXXXXXXX   (または --off)\n")
    return 1


def main():
    stale = check_facts()
    mismatch = check_ga_and_policy()
    broken = []
    # sitemap.py と同じ見方にする。**追跡していない作業中のファイルは、
    # 公開されていない。** 見ても意味が無いし、途中の原稿で赤くなるだけ
    tracked = subprocess.run(["git", "ls-files", "*.html"],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    pages = [ROOT / rel for rel in tracked
             if not any(part in SKIP_DIRS for part in pathlib.Path(rel).parts)]
    for page in sorted(pages):
        s = page.read_text(encoding="utf-8")
        for href in sorted(set(re.findall(r'(?:href|src)="(/[^"]*)"', s))):
            if not targets(href).exists():
                broken.append((page.relative_to(ROOT), href))

    unloaded = check_scripts(sorted(pages))

    if not broken:
        print(f"内部リンク: {len(pages)} ページ、切れているものはありません")
        return 1 if (stale or unloaded or mismatch) else 0

    print("行き先が無いリンク:")
    for page, href in broken:
        print(f"  {page}  →  {href}")
    print("\n公開日がまだ先の記事を指していないか確かめること "
          "(_articles/*.md の date)。")
    return 1

if __name__ == "__main__":
    sys.exit(main())
