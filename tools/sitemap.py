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
for f in sorted(ROOT.rglob("*.html")):
    if ".git" in f.parts:
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
