#!/usr/bin/env python3
"""_goods/*.md から道具箱の商品ページと一覧を作る。

    python3 tools/build_goods.py
    python3 tools/sitemap.py
    python3 tools/check_links.py    ← 公開前に必ず

**予約公開の記事へリンクすると、その日まで404になる。**原稿は _articles/ に
あるので、書いているときは気づけない。機械で見ること。

記事 (build_articles.py) と同じ書き方。違うのは前書きの項目だけ:

    cat:     分類 (カート / 歯みがき / 寝床 …)
    price:   価格の表記 (出典が分かる形で)
    forwho:  こういう人に向く (改行なしの1文)
    notfor:  こういう人には向かない (1文)
    shops:   楽天|URL / Amazon|URL / 公式|URL をカンマ区切り。空なら買う導線を出さない
    draft:   true なら出力しない (書きかけ)

**道具は体に触れるので、よみものと同じ医療の注記 (.med-note) を入れる。**
ハーネスと気管、マットと滑り、歯みがき。どれも「これで治る」に
寄りやすい。読み手が判断を誤らないよう、ページの側で線を引いておく。

**アフィリエイトのリンクを入れたら、ステマ規制の表示 (.ad-note) が
自動で出る。** shops が空のあいだは出ない。
"""
import re, pathlib, html, json, sys, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_articles import chrome, inline, render_body, AUTHOR, BASE, MED_NOTE, APP_URL

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_goods"
OUT = ROOT / "goods"

AD_NOTE = ('<div class="ad-note">当ページのリンクには広告 (アフィリエイトプログラム) が'
           '含まれます。リンクを経由して購入された場合、当サイトに収益が発生することがあります。'
           '掲載しているのは編集部が実際に使ったものだけで、収益の有無で評価を変えることはありません。</div>')

SHOP_CLASS = {"Amazon": "shop-amazon", "楽天": "shop-rakuten",
              "Yahoo": "shop-yahoo", "公式": ""}

# 道具箱にだけ、アプリへの導線が無かった。
#
# よみものは29本中28本に出しているのに、道具箱は0本だった。
# **道具箱に来る人は、買う気で検索してきた人**なので、いちばん濃い。
# 5,000字読んで、店へ行って、それきりになっていた。
#
# 置くのは買う導線の**あと**。先に置くと、このページの目的である
# 購入のクリックを食う。
CTA_TITLE = "替えた日も、続けた日も、記録になります"
CTA_BODY = ("Wandary は、ごはん・うんち・散歩・お薬・気になる様子をワンタップで残せる iOS アプリです。"
            "道具を替えた日を残しておくと、**そのあと何が変わったか**をあとから確かめられます。"
            "歯みがきのように続けるものは、続いた日数がそのまま残ります。")


def app_cta(meta, label="この記事のアプリ"):
    """記事ごとに書き分けたいときは、前書きに cta / ctabody を書く"""
    return f'''
  <div class="app-cta">
    <span class="app-cta-label">{label}</span>
    <span class="app-cta-title">{html.escape(meta.get("cta") or CTA_TITLE)}</span>
    <p>{inline(meta.get("ctabody") or CTA_BODY)}</p>
    <div class="app-cta-actions">
      <a class="btn" href="{APP_URL}">App Store で見る</a>
      <span class="note">無料 · iPhone</span>
    </div>
  </div>
'''


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
    """購入リンクを組み立てる。

    1商品なら          shops: 楽天|URL , Amazon|URL
    複数の商品を出すなら shops: ラベル>楽天|URL , 別のラベル>楽天|URL

    **同じ記事で複数の商品を薦めるとき、ラベルが無いと全部「楽天で見る」に
    なって、どれがどれか分からなくなる。**歯みがきのように道具が3つある記事
    では、ラベルを必ず付けること。
    """
    raw = meta.get("shops", "").strip()
    if not raw:
        return ('<div class="card"><p><strong>購入リンクは準備中です。</strong>'
                'アフィリエイトの審査が通り次第、ここに各ストアへのリンクを出します。</p></div>')

    # ラベルごとにまとめる。順番は書いた順を保つ
    groups = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        label, _, rest = item.rpartition(">") if ">" in item else ("", "", item)
        name, url = rest.split("|", 1)
        cls = SHOP_CLASS.get(name.strip(), "")
        # URL の & は必ずエスケープする。アフィリエイトのリンクは
        # a_id・p_id・pl_id … と & が並ぶので、裸のまま置くとHTMLとして壊れる
        href = html.escape(url.strip(), quote=True)
        slug = meta["slug"] if not label else f'{meta["slug"]}:{label.strip()}'
        btn = (f'<a class="btn shop-btn {cls}" href="{href}" '
               f'target="_blank" rel="noopener sponsored nofollow" '
               f'data-outbound="{html.escape(slug)}">{html.escape(name.strip())}で見る</a>')
        for g in groups:
            if g["label"] == label.strip():
                g["btns"].append(btn)
                break
        else:
            groups.append({"label": label.strip(), "btns": [btn]})

    out = []
    for g in groups:
        row = '<div class="shop-row">\n    ' + "\n    ".join(g["btns"]) + "\n  </div>"
        if g["label"]:
            out.append(f'<div class="shop-group">\n  <p class="shop-label">'
                       f'{html.escape(g["label"])}</p>\n  {row}\n  </div>')
        else:
            out.append(row)
    return "\n  ".join(out) + "\n  " + AD_NOTE


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
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/img/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
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

  {MED_NOTE}
{app_cta(m)}
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
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/img/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
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
{app_cta({}, label="Wandary")}
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
