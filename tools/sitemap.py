#!/usr/bin/env python3
"""sitemap.xml を作り直す。よみものを足したら実行すること。

    python3 tools/sitemap.py

lastmod は git の最終コミット日から取る。手で書くとすぐ嘘になるため。
"""
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
    return sorted(ROOT / rel for rel in out)

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

rows = []
for f in tracked_html():
    if any(part in SKIP_DIRS for part in f.relative_to(ROOT).parts):
        continue
    u = url_for(f)
    if u in SKIP:
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
(ROOT / "sitemap.xml").write_text(xml)
print(f"sitemap.xml: {len(rows)} ページ")
for u, m in rows:
    print(f"  {m}  {u}")
