#!/usr/bin/env python3
"""_goods/*.md から道具箱の商品ページと一覧を作る。

    python3 tools/build_goods.py
    python3 tools/sitemap.py

記事 (build_articles.py) と同じ書き方。違うのは前書きの項目だけ:

    cat:     分類 (カート / 歯みがき / 寝床 …)
    price:   価格の表記 (出典が分かる形で)
    forwho:  こういう人に向く (改行なしの1文)
    notfor:  こういう人には向かない (1文)
    shops:   楽天|URL / Amazon|URL / 公式|URL をカンマ区切り。空なら買う導線を出さない
    draft:   true なら出力しない (書きかけ)

**アフィリエイトのリンクを入れたら、ステマ規制の表示 (.ad-note) が
自動で出る。** shops が空のあいだは出ない。
"""
import re, pathlib, html, json, sys, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_articles import chrome, inline, render_body, AUTHOR, BASE

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_goods"
OUT = ROOT / "goods"

AD_NOTE = ('<div class="ad-note">当ページのリンクには広告 (アフィリエイトプログラム) が'
           '含まれます。リンクを経由して購入された場合、当サイトに収益が発生することがあります。'
           '掲載しているのは編集部が実際に使ったものだけで、収益の有無で評価を変えることはありません。</div>')

SHOP_CLASS = {"Amazon": "shop-amazon", "楽天": "shop-rakuten",
              "Yahoo": "shop-yahoo", "公式": ""}


def parse(path):
    raw = path.read_text()
    head, body = raw.split("\n---\n", 1)
    meta = {}
    for line in head.strip().splitlines():
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    meta["slug"] = path.stem
    meta["body"] = body.strip()
    for need in ("cat", "date", "title", "lead", "forwho", "notfor"):
        if need not in meta:
            raise SystemExit(f"{path.name}: {need} がありません")
    return meta


def shops(meta):
    raw = meta.get("shops", "").strip()
    if not raw:
        return ('<div class="card"><p><strong>購入リンクは準備中です。</strong>'
                'アフィリエイトの審査が通り次第、ここに各ストアへのリンクを出します。</p></div>')
    btns = []
    for item in raw.split(","):
        name, url = item.split("|", 1)
        cls = SHOP_CLASS.get(name.strip(), "")
        btns.append(f'<a class="btn shop-btn {cls}" href="{url.strip()}" '
                    f'target="_blank" rel="noopener sponsored" '
                    f'data-outbound="{meta["slug"]}">{html.escape(name.strip())}で見る</a>')
    return f'<div class="shop-row">\n    ' + "\n    ".join(btns) + "\n  </div>\n  " + AD_NOTE


def verdict(meta):
    return f'''  <div class="pick-note">
    <strong>こういう人に向きます</strong>
    <p>{inline(meta["forwho"])}</p>
  </div>
  <div class="pick-note" style="border-left-color:#C58A2E; background:#FBF6EC;">
    <strong style="color:#8A6A2E;">こういう人には向きません</strong>
    <p>{inline(meta["notfor"])}</p>
  </div>'''


def build(preview_dir=None):
    """preview_dir を渡すと、下書きも含めてそこに書き出す (公開はしない)"""
    global OUT
    head, foot = chrome()
    today = datetime.date.today().isoformat()
    everything = [parse(p) for p in sorted(SRC.glob("*.md"))]
    if preview_dir:
        OUT = pathlib.Path(preview_dir); OUT.mkdir(parents=True, exist_ok=True)
        metas, waiting = everything, []
    else:
        metas = [m for m in everything
                 if m["date"] <= today and m.get("draft", "").lower() != "true"]
        waiting = [m for m in everything if m not in metas]
    metas.sort(key=lambda m: (m["date"], m["slug"]), reverse=True)

    for m in metas:
        page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(m["title"])} | Wandary 編集部の道具箱</title>
<meta name="description" content="{html.escape(m["lead"], quote=True)}">
<link rel="canonical" href="{BASE}/goods/{m["slug"]}.html">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(m["title"], quote=True)}">
<meta property="og:description" content="{html.escape(m["lead"], quote=True)}">
<meta property="og:url" content="{BASE}/goods/{m["slug"]}.html">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
</head>
<body>
{head}
<main class="article">
  <div class="sheet">
  <div class="article-head">
    <span class="pick-cat">{m["cat"]}</span>
    <span class="article-date">{m["date"].replace("-", ".")}</span>
  </div>
  <h1 class="article-title">{html.escape(m["title"])}</h1>
  <p class="article-lead">{inline(m["lead"])}</p>

{verdict(m)}

{render_body(m["body"])}

  {shops(m)}

  {AUTHOR}
  </div>
</main>
{foot}
</body>
</html>
'''
        (OUT / f'{m["slug"]}.html').write_text(page)

    # ── 一覧 ──
    if metas:
        items = "\n".join(
            f'    <li class="pick-item">\n'
            f'      <p class="pick-cat">{m["cat"]}</p>\n'
            f'      <a href="{m["slug"]}.html">{html.escape(m["title"])}</a>\n'
            f'      <p>{html.escape(m["lead"])}</p>\n'
            f'    </li>'
            for m in metas)
        body = f'  <ul class="pick-list">\n{items}\n  </ul>'
    else:
        body = ('  <div class="card" style="text-align:center; padding:34px 24px;">\n'
                '    <p style="font-weight:700; color:#1E242C;">ただいま準備中です</p>\n'
                '    <p style="margin-top:6px;">実際に使ったものだけを載せたいので、ひとつずつ書いています。<br>公開まで、もう少しお待ちください。</p>\n'
                '    <p style="margin-top:18px;"><a class="btn" href="/knowledge/">よみものを読む</a></p>\n'
                '  </div>')

    idx = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>編集部の道具箱 | Wandary</title>
<meta name="description" content="チワワと20年暮らしてきた Wandary 編集部が、実際に使ってきた道具と選び方をまとめています。">
<link rel="canonical" href="{BASE}/goods/">
<meta property="og:type" content="article">
<meta property="og:title" content="編集部の道具箱 | Wandary">
<meta property="og:description" content="チワワと20年暮らしてきた Wandary 編集部が、実際に使ってきた道具と選び方をまとめています。">
<meta property="og:url" content="{BASE}/goods/">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
</head>
<body>
{head}
<main class="article">
  <div class="sheet">
  <h1 class="page-title">🧰 編集部の道具箱</h1>
  <p>チワワと20年、4匹と暮らしてきた Wandary 編集部が、実際に使ってきた道具と、その選び方をまとめています。</p>
  <p>品ぞろえは目指していません。<strong>本当に使ったものだけ</strong>を、少しずつ増やしていきます。合わなかったものも、そのまま書きます。</p>

{body}
  {AUTHOR}
  </div>
</main>
{foot}
</body>
</html>
'''
    (OUT / "index.html").write_text(idx)
    print(f"道具箱 {len(metas)}件 + 一覧を書き出しました")
    for m in metas:
        print(f'  {m["date"]}  [{m["cat"]}]  {m["slug"]}.html  {m["title"]}')
    if waiting:
        print(f"\n下書き・公開待ち {len(waiting)}件")
        for m in waiting:
            print(f'  {m["date"]}  {m["slug"]}  {m["title"]}')


if __name__ == "__main__":
    # 下書きの見た目を確かめる: python3 tools/build_goods.py --preview <dir>
    if "--preview" in sys.argv:
        build(sys.argv[sys.argv.index("--preview") + 1])
    else:
        build()
