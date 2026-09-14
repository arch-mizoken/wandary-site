#!/usr/bin/env python3
"""_articles/*.md から knowledge/ の記事HTMLと一覧を作る。

    python3 tools/build_articles.py
    python3 tools/sitemap.py        # 続けて実行すること

ヘッダとフッタは index.html から抜き出して使う。テンプレートを二重に
持つと、ナビを足したときに記事側だけ古くなるため。

本文の記法は既存記事が使っているものだけ:
    ## 見出し      → <h2>  (### は <h3>)
    - 箇条書き     → <ul><li>
    **強調**       → <strong>
    [文字](URL)    → <a>
    空行区切り     → <p>
"""
import re, pathlib, html, json, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_articles"
OUT = ROOT / "knowledge"
BASE = "https://wandary.jp"

MED_NOTE = ('<p class="med-note">ⓘ 一般的な情報の提供であり、診断や治療の助言ではありません。'
            '気になる症状があるときは、記録を持ってかかりつけの獣医師にご相談ください。</p>')
APP_URL = "https://apps.apple.com/jp/app/id6792701313"

AUTHOR = '''<div class="author">
    <img src="/img/mark.png" alt="" width="36" height="36">
    <div class="who">
      <strong>文 · Wandary編集部</strong>
      <span>チワワと20年、4匹と暮らしてきました。獣医師ではありません。このページは飼い主としての経験と、一般に知られている情報をもとに書いています。</span>
    </div>
  </div>'''


def chrome():
    """ナビの二重管理をやめる — index.html のヘッダとフッタをそのまま使う"""
    s = (ROOT / "index.html").read_text()
    head = re.search(r"<header>.*?</header>", s, re.S).group(0)
    foot = re.search(r"<footer>.*?</footer>", s, re.S).group(0)
    # 記事は1階層下なので相対パスを直す (ルート相対なら不要だが念のため)
    return head, foot


def parse(path):
    raw = path.read_text()
    head, body = raw.split("\n---\n", 1)
    meta = {}
    for line in head.strip().splitlines():
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    meta["slug"] = path.stem
    meta["body"] = body.strip()
    for need in ("cat", "date", "title", "lead", "cta", "ctabody"):
        if need not in meta:
            raise SystemExit(f"{path.name}: {need} がありません")
    return meta


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t


def table(block):
    """| a | b |  の3行以上を <table> にする。2行目の |---| は捨てる"""
    rows = [r.strip().strip("|").split("|") for r in block.splitlines()]
    head, body = rows[0], rows[2:]
    th = "".join(f"<th>{inline(c.strip())}</th>" for c in head)
    trs = "\n".join(
        "    <tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in r) + "</tr>"
        for r in body)
    return f'  <table>\n    <tr>{th}</tr>\n{trs}\n  </table>'


def quote(block):
    """> で始まる塊。書きかけの【要記入】もここに入る"""
    lines = [l.lstrip(">").strip() for l in block.splitlines()]
    ps = "\n".join(f"    <p>{inline(l)}</p>" for l in lines if l)
    return f'  <div class="card">\n{ps}\n  </div>'


def render_body(md):
    out, bullets = [], []

    def flush():
        if bullets:
            items = "\n".join(f"    <li>{inline(b)}</li>" for b in bullets)
            out.append(f"  <ul>\n{items}\n  </ul>")
            bullets.clear()

    for block in md.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            flush()
            out.append(f"  <h3>{inline(block[4:].strip())}</h3>")
        elif block.startswith("## "):
            flush()
            out.append(f"  <h2>{inline(block[3:].strip())}</h2>")
        elif block.startswith("|") and block.count("\n") >= 2:
            flush()
            out.append(table(block))
        elif block.startswith(">"):
            flush()
            out.append(quote(block))
        elif block.startswith("- "):
            for line in block.splitlines():
                bullets.append(line[2:].strip())
            flush()
        else:
            flush()
            out.append(f"  <p>{inline(block.replace(chr(10), ''))}</p>")
    flush()
    return "\n".join(out)


def related(meta, all_meta, n=3):
    """同じカテゴリの新しい順。無ければ他カテゴリで埋める"""
    same = [m for m in all_meta if m["cat"] == meta["cat"] and m["slug"] != meta["slug"]]
    rest = [m for m in all_meta if m["cat"] != meta["cat"] and m["slug"] != meta["slug"]]
    picked = (same + rest)[:n]
    if not picked:
        return ""
    items = "\n".join(
        f'    <li class="pick-item">\n'
        f'      <a href="{m["slug"]}.html">{html.escape(m["title"])}</a>\n'
        f'      <p>{html.escape(m["lead"])}</p>\n'
        f'    </li>'
        for m in picked
    )
    return f'''
  <div class="related">
    <p class="related-label">つぎに読む</p>
    <ul class="pick-list">
{items}
    </ul>
  </div>
'''


def app_cta(meta):
    """記事ごとのアプリ導線。ここがこのサイトの出口なので、記事ごとに書き分ける"""
    return f'''
  <div class="app-cta">
    <span class="app-cta-label">この記事のアプリ</span>
    <span class="app-cta-title">{html.escape(meta["cta"])}</span>
    <p>{inline(meta["ctabody"])}</p>
    <div class="app-cta-actions">
      <a class="btn" href="{APP_URL}">App Store で見る</a>
      <span class="note">無料 · iPhone</span>
    </div>
  </div>
'''


def jsonld(meta):
    d = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": meta["title"],
        "description": meta["lead"],
        "datePublished": meta["date"],
        "author": {"@type": "Organization", "name": "Wandary編集部"},
        "publisher": {"@type": "Organization", "name": "Wandary",
                      "logo": {"@type": "ImageObject", "url": f"{BASE}/img/mark.png"}},
        "mainEntityOfPage": f"{BASE}/knowledge/{meta['slug']}.html",
        "image": f"{BASE}/img/ogp.png",
        "inLanguage": "ja",
    }
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>"


def build():
    head, foot = chrome()
    today = datetime.date.today().isoformat()
    everything = [parse(p) for p in sorted(SRC.glob("*.md"))]
    # 日付が未来の記事はまだ出さない。4本 → 100本を一度に公開すると
    # 「スケーリングされたコンテンツの不正使用」に当たりやすく、
    # ペナルティはドメイン全体 (LP・サポートも) に効く。書きためて小出しにする
    metas = [m for m in everything if m["date"] <= today]
    waiting = [m for m in everything if m["date"] > today]
    metas.sort(key=lambda m: (m["date"], m["slug"]), reverse=True)

    for m in metas:
        page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(m["title"])} | Wandary</title>
<meta name="description" content="{html.escape(m["lead"], quote=True)}">
<link rel="canonical" href="{BASE}/knowledge/{m["slug"]}.html">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(m["title"], quote=True)}">
<meta property="og:description" content="{html.escape(m["lead"], quote=True)}">
<meta property="og:url" content="{BASE}/knowledge/{m["slug"]}.html">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
{jsonld(m)}
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

{render_body(m["body"])}

  {MED_NOTE}

  {AUTHOR}
  </div>
{related(m, metas)}{app_cta(m)}</main>
{foot}
</body>
</html>
'''
        (OUT / f'{m["slug"]}.html').write_text(page)

    # ── 一覧 ──
    items = "\n".join(
        f'    <li class="pick-item">\n'
        f'      <p class="pick-cat">{m["cat"]}</p>\n'
        f'      <a href="{m["slug"]}.html">{html.escape(m["title"])}</a>\n'
        f'      <p>{html.escape(m["lead"])}</p>\n'
        f'    </li>'
        for m in metas
    )
    idx = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>よみもの | Wandary</title>
<meta name="description" content="犬と暮らすうえで知っておきたいことを、飼い主の目線でまとめています。">
<link rel="canonical" href="{BASE}/knowledge/">
<meta property="og:type" content="website">
<meta property="og:title" content="よみもの | Wandary">
<meta property="og:description" content="犬と暮らすうえで知っておきたいことを、飼い主の目線でまとめています。">
<meta property="og:url" content="{BASE}/knowledge/">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
</head>
<body>
{head}
<main>
  <div class="sheet">
  <h1 class="page-title">よみもの</h1>
  <p>犬と暮らすうえで知っておきたいことを、飼い主の目線でまとめています。
  数をそろえるより、一本ずつ書ききることを大事にしています。</p>
  <ul class="pick-list">
{items}
  </ul>
  {MED_NOTE}
  </div>
</main>
{foot}
</body>
</html>
'''
    (OUT / "index.html").write_text(idx)
    # 予約ぶんが残っていると、消し忘れた HTML が居座る
    live = {m["slug"] for m in metas}
    for f in OUT.glob("*.html"):
        if f.stem != "index" and f.stem not in live:
            f.unlink()
            print(f"  (取り下げ) {f.name}")

    print(f"記事 {len(metas)}本 + 一覧を書き出しました")
    for m in metas:
        print(f'  {m["date"]}  [{m["cat"]}]  {m["slug"]}.html  {m["title"]}')
    if waiting:
        print(f"\n公開待ち {len(waiting)}本 (その日が来たら自動で出ます)")
        for m in sorted(waiting, key=lambda m: m["date"]):
            print(f'  {m["date"]}  [{m["cat"]}]  {m["title"]}')


if __name__ == "__main__":
    build()
