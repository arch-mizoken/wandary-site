#!/usr/bin/env python3
"""sitemap.xml を作り直す。よみものを足したら実行すること。

    python3 tools/sitemap.py

lastmod は git の最終コミット日から取る。手で書くとすぐ嘘になるため。
"""
import sys
import re
import subprocess, pathlib, datetime

BASE = "https://wandary.jp"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# 出したくないページはここに。いまは無し
SKIP = set()

# **このリポジトリにあっても、wandary.jp のページではないもの。**
# nyandary は開発中の別サイトで、いずれ別ドメインへ移す。
# sitemap に入れると、Google に「wandary.jp の一部です」と申告することになり、
# 移したあとリダイレクトで後始末する羽目になる
SKIP_DIRS = {"nyandary"}


def tracked_html():
    """**git が追跡している HTML だけ**を集める。

    公開されているのは、コミットされたものだけ。作業中のファイルを
    拾うと、**本番に無い URL を Google に案内する**ことになる。

    実際 2026-09-23、開発中の別サイト (別ドメインへ移す予定のもの) が
    作業フォルダに置かれていて、そのまま sitemap に入って公開された。
    行き先は 404 だった。名前で除外すると、次の1件でまた同じことが起きる。
    """
    out = subprocess.run(["git", "ls-files", "*.html"],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    # set でまとめる。rebase で衝突している最中は、git ls-files が
    # 同じパスを stage ごとに何度も返すので、同じURLが二重に載る
    return sorted({ROOT / rel for rel in out})

# 検索から来てほしい順。Google は priority をほぼ見ないが、
# 「どれが主役か」を書き残しておく意味で付けている
PRIORITY = {
    "/lp.html": "1.0",
    "/": "0.9",
    "/knowledge/": "0.9",
    "/goods/": "0.8",
    "/updates/": "0.6",
}

def url_for(path: pathlib.Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel

def lastmod(path: pathlib.Path) -> str:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", str(path)],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    return out or datetime.date.today().isoformat()

NOINDEX = re.compile(r'<meta\s+name=["\']robots["\'][^>]*noindex', re.I)


def is_noindex(path: pathlib.Path) -> bool:
    """noindex のページは地図に載せない。

    載せると「来てください」と言いながら「載せないで」と言うことになる。
    Search Console には「noindex により除外」が並ぶだけで、誰の得にもならない。
    **ページ側の宣言をそのまま信じる**ので、一覧を手で保つ必要がない
    """
    return bool(NOINDEX.search(path.read_text(encoding="utf-8", errors="ignore")))


rows = []
for f in tracked_html():
    if any(part in SKIP_DIRS for part in f.relative_to(ROOT).parts):
        continue
    u = url_for(f)
    if u in SKIP:
        continue
    if is_noindex(f):
        continue
    rows.append((u, lastmod(f)))

# 主役から並べる
rows.sort(key=lambda r: (-float(PRIORITY.get(r[0], "0.5")), r[0]))

body = "\n".join(
    f'  <url>\n'
    f'    <loc>{BASE}{u}</loc>\n'
    f'    <lastmod>{m}</lastmod>\n'
    f'    <priority>{PRIORITY.get(u, "0.5")}</priority>\n'
    f'  </url>'
    for u, m in rows
)
xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
'''
# いちど地図に載せた URL が消えるのは、たいてい事故。
# 記事の振り分けを変えたり、生成の条件を変えたりしたときに起きる。
# 検索結果に出ている URL が 404 になるので、**書き換える前に止める。**
# わざと消すときだけ --allow-drop を付ける (noindex にした、記事を取り下げた)
out = ROOT / "sitemap.xml"
if out.exists():
    before = set(re.findall(r"<loc>(.*?)</loc>", out.read_text(encoding="utf-8")))
    gone = sorted(before - {f"{BASE}{u}" for u, _ in rows})
    if gone and "--allow-drop" not in sys.argv:
        print("地図から消えようとしている URL があります:")
        for u in gone:
            print(f"  - {u}")
        print("\nわざと消すなら --allow-drop を付けてください。")
        sys.exit(1)
    for u in gone:
        print(f"  ※ 地図から外しました: {u}")

out.write_text(xml)
print(f"sitemap.xml: {len(rows)} ページ")
for u, m in rows:
    print(f"  {m}  {u}")
