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
    <img src="/img/logo-head.svg" alt="" width="36" height="36">
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


def _grams(text, n=2):
    """日本語を、文字の2つ組にして数える。

    形態素解析を入れずに「話が近いか」を測るための、いちばん安い方法。
    「ワクチン」と「予防接種」は繋がらないが、**同じ語が出てくる記事同士は繋がる。**
    辞書も外部ライブラリも要らないのが、この道具の値打ち。
    """
    t = re.sub(r"[\s、。「」（）()・:：/／\-–—\[\]｜|!！?？]+", "", text)
    return {t[i:i+n] for i in range(len(t) - n + 1)}


def related(meta, all_meta, n=3):
    """つぎに読む記事を選ぶ。

    **カテゴリの新しい順ではいけない。**公開が25本でカテゴリが11もあると、
    同じカテゴリに兄弟がおらず、毎回「他カテゴリの新しい3本」で埋まる。
    実際そうなっていて、ワクチンの記事から保護犬と保険に送っていた。
    読み手にも検索エンジンにも、意味がない。

    だから**本文の重なりで測る**。前書きに related: を書けば、そちらが勝つ。
    """
    others = [m for m in all_meta if m["slug"] != meta["slug"]]

    # 手で指定してあれば、それを最優先 (related: slug, slug)
    manual = [x.strip() for x in meta.get("related", "").split(",") if x.strip()]
    by_slug = {m["slug"]: m for m in others}
    picked = [by_slug[x] for x in manual if x in by_slug]

    if len(picked) < n:
        mine = _grams(meta["title"] + meta["lead"] + meta["body"])
        scored = []
        for m in others:
            if m in picked:
                continue
            theirs = _grams(m["title"] + m["lead"] + m["body"])
            if not mine or not theirs:
                continue
            # Jaccard。長い記事が有利にならないよう、和で割る
            overlap = len(mine & theirs) / len(mine | theirs)
            # 同じカテゴリは、それ自体が「近い」という編集判断なので足す
            if m["cat"] == meta["cat"]:
                overlap += 0.05
            scored.append((overlap, m["date"], m["slug"], m))
        scored.sort(key=lambda x: (-x[0], x[1]))
        picked += [x[3] for x in scored[: n - len(picked)]]

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


def search_title(meta):
    """検索結果に出す題。

    **ページの見出し (h1) と、検索結果の題は、別でいい。**

    このサイトの題は「聞きたいことは、その場では出てきません」のように
    書かれている。読み物としては良いが、**誰もその言葉では検索しない。**
    見出しを検索語に寄せて書き換えると、今度はサイトの声が消える。

    だから分ける。前書きに seotitle: があれば <title> はそちら、
    ページの中は title: のまま。無ければ両方 title:。

    日本語の検索結果に出るのは、およそ30文字まで。「 | Wandary」で9文字使うので、
    seotitle は**22文字まで**を目安にする。
    """
    return meta.get("seotitle", meta["title"]).strip()


def with_toc(body_html, least=5):
    """見出しに印をつけ、数が多ければ目次を作る。

    長い記事は、**開いた瞬間に「自分の知りたいことが書いてあるか」が分からない**と
    そのまま閉じられる。目次があると、そこで判断してもらえる。
    検索結果に見出しへの飛び先が出ることもある。

    見出しが少ない記事には付けない。3つしかない目次は、ただの重複。
    """
    heads = re.findall(r"  <h2>(.*?)</h2>", body_html)
    if len(heads) < least:
        return "", body_html
    out, i = [], 0
    for line in body_html.split("\n"):
        m = re.match(r"  <h2>(.*?)</h2>", line)
        if m:
            i += 1
            out.append(f'  <h2 id="s{i}">{m.group(1)}</h2>')
        else:
            out.append(line)
    items = "\n".join(
        f'      <li><a href="#s{n}">{h}</a></li>' for n, h in enumerate(heads, 1))
    toc = f'''  <nav class="toc" aria-label="目次">
    <p class="toc-label">この記事の中身</p>
    <ol>
{items}
    </ol>
  </nav>
'''
    return toc, "\n".join(out)


def search_description(meta, low=80, cap=118):
    """検索結果に出る説明文。

    **lead だけだと短すぎる。**37〜53字で、日本語の表示枠 (およそ90〜120字) の
    半分も使っていなかった。空けておくと Google が本文から勝手に拾うので、
    **こちらで決めた文を出したほうがいい。**

    足りないぶんは本文の頭から、文の切れ目で足す。途中で切らない。
    """
    desc = meta["lead"].strip()
    if len(desc) >= low:
        return desc[:cap]
    first = next((b.strip() for b in meta["body"].split("\n\n")
                  if b.strip() and not b.strip().startswith(("#", "-", "|", ">"))), "")
    first = re.sub(r"\*\*", "", first)
    first = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", first)
    for sentence in re.findall(r"[^。]+。", first):
        if len(desc) + len(sentence) > cap:
            break
        desc += sentence
        if len(desc) >= low:
            break
    return desc


def jsonld(meta):
    d = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": meta["title"],
        "description": search_description(meta),
        "datePublished": meta["date"],
        # 更新日。前書きに updated: があればそれ、無ければ公開日。
        # 無いと「いつの情報か」を検索エンジンが判断できない
        "dateModified": meta.get("updated", meta["date"]),
        "author": {"@type": "Organization", "name": "Wandary編集部"},
        "publisher": {"@type": "Organization", "name": "Wandary",
                      "logo": {"@type": "ImageObject", "url": f"{BASE}/img/mark.png"}},
        "mainEntityOfPage": f"{BASE}/knowledge/{meta['slug']}.html",
        "image": f"{BASE}/img/ogp.png",
        "inLanguage": "ja",
    }
    # パンくず。検索結果に階層が出て、どこの何かが伝わる
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "よみもの", "item": f"{BASE}/knowledge/"},
            {"@type": "ListItem", "position": 3, "name": meta["title"],
             "item": f"{BASE}/knowledge/{meta['slug']}.html"},
        ],
    }
    return ('<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>\n"
            '<script type="application/ld+json">' + json.dumps(crumbs, ensure_ascii=False) + "</script>")


# ── まとめページ (ハブ) ──
#
# 記事を100本並べても、1本読んで帰られたら1本ぶんの価値しかない。
# クラスタごとの入口を作って、そこに内部リンクを集める。
#
# ハブは一覧だけだと中身が薄く、検索にも拾われない。導入の文章が本体で、
# 一覧はそのあと。ここは手で書くこと (記事から自動生成しない)。
HUBS = [
    {
        "slug": "paperwork", "cats": ["てつづき"],
        "title": "犬の登録・届出・お金のこと",
        "lead": "迎えたときと、毎年と、暮らしが変わったとき。法律で決まっている手続きと、実際にかかるお金をまとめています。",
        "intro": [
            "犬を迎えると、法律で決まっている手続きがいくつかあります。生後91日を過ぎたら市区町村への登録、毎年の狂犬病予防注射、マイクロチップの情報登録。",
            "どれも一生に一度か、年に一度きりです。**誰も教えてくれないのに、やっていないと罰則がある**という種類のものばかりで、気づいたときには期限を過ぎていることがあります。引っ越したときや、飼い主が変わったときにも届け出が要ります。",
            "ここでは「いつ・どこで・いくら」で書いています。ただし窓口も手数料も自治体ごとに違うので、最後はかならずお住まいの市区町村にご確認ください。",
        ],
        "sections": [
            {"h": "迎えた年に、やること", "p": [
                """順番があります。**まず市区町村への登録、つぎに狂犬病予防注射、そしてマイクロチップの情報登録。**どれも期限が決まっていて、しかも誰も教えてくれません。""",
                """- **市区町村への登録** — 生後91日以上の犬を迎えたら、**30日以内**に1回。3,000円前後。引っ越さないかぎり、生涯そのまま
- **狂犬病予防注射** — 毎年1回。3,000円前後。注射済票の交付に550円前後
- **マイクロチップの情報登録** — 引き渡しから**30日以内**。オンライン300円、紙の申請1,000円""",
                """ここでいちばん落としやすいのが、**3つめ**です。マイクロチップは「入れた」と「登録した」が別の手続きで、入れただけでは、拾われても連絡が来ません。""",
            ]},
            {"h": "毎年くるものと、その金額", "p": [
                """一度きりのものが終わると、つぎは毎年のものが来ます。**予防だけで、年に数万円**。ここを知らないと、春先に驚きます。""",
                """狂犬病予防注射は、4月から6月にかけてが本番です。**集合注射**といって、公民館などで安く受けられる機会を設けている自治体もあります。案内のはがきが届くのは、**登録してある住所**です。""",
                """そこに混合ワクチンと、フィラリア・ノミダニの予防が重なります。**同じ時期にまとまって出ていく**ので、年間でいくらかかるのかを一度だけ数えておくと、毎年慌てずに済みます。""",
            ]},
            {"h": "引っ越したら、直すところは3つ", "p": [
                """住所が変わると、**自動では何も変わりません。**自分で3か所を直すことになります。""",
                """- **市区町村の登録** — 転入先に出します。転出元ではありません
- **マイクロチップの登録情報** — 自分で直します。ここを忘れる人がいちばん多い
- **かかりつけの引き継ぎ** — これまでの経過を、新しい病院に渡せる形にしておく""",
                """**狂犬病予防注射の案内は、届け出をしないと来ません。**来ないから忘れる、という順で抜けます。""",
            ]},
        ],
    },
    {
        "slug": "signs", "cats": ["きづく"],
        "title": "「いつもと違う」に気づくために",
        "lead": "犬は言葉で伝えられません。そばにいる人が最初のサインに気づくための、見るべき場所と残し方。",
        "intro": [
            "犬は「つらい」と言えません。だから、毎日そばにいる人の小さな気づきが、いちばん早いサインになります。",
            "ただ、気づくには「いつも」を知っている必要があります。そしてここが難しいところで、**毎日会っている家族ほど、少しずつの変化には気づけません**。半年前の写真を見て、はじめて痩せたと分かる。そういうことが実際に起きます。",
            "比べられる形で残しておくこと。体重、水を飲む量、寝ているときの呼吸数。どれも1分もかからないのに、あとから効いてきます。",
        ],
        "sections": [
            {"h": "毎日会っているほど、気づけない", "p": [
                """犬は「つらい」と言えません。だから、そばにいる人の気づきが最初のサインになります。""",
                """ただ、**毎日会っている家族ほど、少しずつの変化には気づけません。**半年前の写真を見て、はじめて痩せたと分かる。そういうことが実際に起きます。""",
            ]},
            {"h": "比べられる形で残しておく", "p": [
                """気づくには「いつも」を知っている必要があります。そして「いつも」は、**比べられる形**でしか手に入りません。""",
                """体重、水を飲む量、寝ているときの呼吸数。**どれも1分もかからない**のに、あとから効いてきます。""",
            ]},
        ],
    },
    {
        "slug": "vet", "cats": ["びょういん", "けんこう"],
        "title": "動物病院とのつきあい方",
        "lead": "診察は5分から10分。その短い時間で伝えきるために、家での様子をどう持っていくか。",
        "intro": [
            "診察室に入った瞬間、頭が真っ白になったことはありませんか。",
            "家では気になっていたのに、先生を前にすると「なんとなく元気がなくて……」としか出てこない。そして帰り道に、聞きたかったことを思い出す。**これは記憶力の問題ではなく、その場で思い出す形になっていないだけ**です。",
            "獣医師が知りたいのは、飼い主の解釈ではなく、その手前の事実であることが多い。いつから、どのくらい、ほかに何が起きていたか。ここでは、聞かれることと、こちらから聞いておくことをまとめています。",
        ],
        "sections": [
            {"h": "診察は5分から10分しかない", "p": [
                """動物病院の診察は、思っているより短いものです。**その中で、家で起きていたことを伝えきる**必要があります。""",
                """家では気になっていたのに、先生を前にすると「なんとなく元気がなくて……」としか出てこない。そして帰り道に、聞きたかったことを思い出す。**これは記憶力の問題ではありません。**その場で思い出す形になっていないだけです。""",
            ]},
            {"h": "獣医師が知りたいのは、解釈より先に事実", "p": [
                """「元気がない」は解釈です。その手前に、**いつから・どのくらい・ほかに何が起きていたか**という事実があります。""",
                """たとえば「あまり食べない」より「**朝と晩、2食続けて残した。おとといから**」のほうが、はるかに早く話が進みます。吐いたなら、回数と、何が出たか。うんちなら、言葉より**写真**のほうが正確です。""",
                """解釈を伝えるなというのではありません。**事実を先に置くと、解釈も信じてもらえる**という順番の話です。""",
            ]},
            {"h": "帰り道で思い出さないために", "p": [
                """聞きたいことは、診察室では出てきません。**前の晩に書き出しておく**のがいちばん確実です。""",
                """3つで足ります。**いま困っていること / 続けていいか迷っていること / 次はいつ来るか。**この3つを紙かスマホに書いておくだけで、帰り道の後悔が減ります。""",
            ]},
        ],
    },
    {
        "slug": "records", "cats": ["きろく", "たとうがい"],
        "title": "犬の記録の残し方",
        "lead": "毎日つけることより、続くことのほうが大事です。何を残すと、あとから効くのか。",
        "intro": [
            "記録は、つけはじめるより続けるほうが難しい。三日坊主で終わったノートが、家に何冊かある方も多いと思います。",
            "20年つけてきて、結局いちばん役に立ったのは**「何もなかった日」の記録**でした。異常があった日だけを書いていると、それが異常なのかどうかを判断する基準が手元に無い。ふつうの日が並んでいてはじめて、違う日が違って見えます。",
            "だから、空欄の日があっていい。ひとことだけの日があっていい。ここでは、どこまで書けば十分なのかを書いています。",
        ],
        "sections": [
            {"h": "続かない理由は、だいたい同じ", "p": [
                """三日坊主で終わったノートが、家に何冊かある方も多いと思います。**原因は根気ではなく、決め方**であることが多いです。""",
                """毎日きちんと書こうとすると、書けなかった日に罪悪感が出ます。そして罪悪感が出た記録は、続きません。**空欄の日があっていい**と決めておくだけで、半年後に残っている量がまるで変わります。""",
            ]},
            {"h": "何を残すと、あとから効くのか", "p": [
                """20年つけてきて、結局いちばん役に立ったのは**「何もなかった日」の記録**でした。""",
                """異常があった日だけを書いていると、**それが異常なのかを判断する基準が手元にありません。**ふつうの日が並んでいて、はじめて違う日が違って見えます。""",
                """数字で残せるものは、数字のほうが強い。**体重、水を飲む量、寝ているときの呼吸数。**どれも1分もかからないのに、半年後に効いてきます。""",
            ]},
            {"h": "2匹目から、記録は急に難しくなる", "p": [
                """多頭で困るのは量ではなく、**取り違え**です。どちらの子の記録だったか分からなくなると、その記録は無かったことになります。""",
                """**入れる前に「どの子か」が決まっている形**にしておくこと。あとから見分ける仕組みにすると、必ずどこかで混ざります。""",
            ]},
        ],
    },
    {
        "slug": "senior", "cats": ["シニア"],
        "title": "シニア犬と暮らす",
        "lead": "小型犬なら7歳ごろから。その日を境に何かが変わるわけではありませんが、見る場所は変わります。",
        "intro": [
            "小型犬なら7歳、大型犬なら5〜6歳あたりから「シニア」と呼ばれます。ただ、誕生日を境に何かが変わるわけではありません。",
            "変わるのは、**同じことが少しずつできなくなっていく速さ**です。散歩から帰る時間が少し早くなる。段差の前で一瞬止まる。呼んでも振り向かないことが増える。ひとつずつは「歳だから」で流せてしまうものばかりで、だからこそ記録が効きます。",
            "ここでは、この時期に見ておくことと、もっと早くやっておけばよかったと思ったことを書いています。",
        ],
        "sections": [
            {"h": "シニアは、ある日から始まらない", "p": [
                """年齢で線が引かれますが、**体のほうは、その日を境に変わったりしません。**少しずつ、気づかないうちに変わっていきます。""",
                """だからこそ、**変わる前の記録**が効きます。何歳から測り始めたかで、後から見える量がまったく違います。""",
            ]},
            {"h": "増えるのは、通院と薬", "p": [
                """シニアになると、病院に行く回数と、飲んでいる薬が増えます。**どちらも、記録していないと積み上がりません。**""",
                """いつから何を飲んでいて、いつ何を言われたか。**これを持っていけるかどうかで、診察の中身が変わります。**""",
            ]},
        ],
    },
    {
        "slug": "puppy", "cats": ["こいぬ"],
        "title": "子犬を迎えた最初の半年",
        "lead": "期限のある予定が、短い間に集まっています。何を、いつまでに。",
        "intro": [
            "最初の半年は、期限のある予定が集中します。ワクチンの2回目・3回目、市区町村への登録、フィラリアの開始、避妊去勢の検討。",
            "同時に、いちばん不安な時期でもあります。食べない、下痢をする、夜鳴きする。**そのほとんどは様子を見ていい一方で、子犬は悪くなるのが早い**ので、どこからが病院なのかの線引きが要ります。",
            "ここでは、この時期に実際に起きることと、その線引きを書いています。",
        ],
        "sections": [
            {"h": "最初の1週間は、やらないことを決める", "p": [
                """迎えたばかりの子犬には、やってあげたいことが山ほどあります。**ただ、最初の週にいちばん効くのは「やらないこと」を決めるほうです。**""",
                """環境が変わったばかりの体に、来客と、長い散歩と、新しいしつけを一度に足さない。**落ち着くまで待つ**ほうが、結局は早く進みます。""",
            ]},
            {"h": "ワクチンが済むまでの過ごし方", "p": [
                """ワクチンのプログラムが終わるまでは、行ける場所と会える相手が限られます。**先住犬がいる家では、一定の距離を置くよう言われることもあります。**""",
                """回数も期間も子によって違うので、**かかりつけの獣医師の指示に従ってください。**ここでは、その期間をどう過ごすかを書いています。""",
            ]},
        ],
    },
    {
        "slug": "living", "cats": ["くらし", "ごはん"],
        "title": "犬との暮らしで、つまずくところ",
        "lead": "留守番、引っ越し、車、来客、赤ちゃん。そのつど調べ直すことになりがちな話。",
        "intro": [
            "犬と暮らしていると、想定していなかった場面が次々に出てきます。留守番は何時間までか。引っ越しで何を先にやるか。車に酔う子をどうするか。",
            "どれも「そのとき」に調べることになって、**慌てて調べた情報はたいてい間に合いません**。引っ越しも赤ちゃんも、準備に数か月かかるものだからです。",
            "ここでは、先に知っておくと楽になる話をまとめています。",
        ],
        "sections": [
            {"h": "「そのとき」に調べると、間に合わない", "p": [
                """留守番は何時間までか。引っ越しで何を先にやるか。車に酔う子をどうするか。**どれも、必要になってから調べることになります。**""",
                """そして慌てて調べた情報は、たいてい間に合いません。**引っ越しも、赤ちゃんを迎えるのも、準備に数か月かかる**ものだからです。先に知っておくだけで、選べる手が増えます。""",
            ]},
            {"h": "時間ではなく、条件で決める", "p": [
                """「何時間まで」「何分歩く」のような**時間の物差しは、当てになりません。**その日の条件で変わるからです。""",
                """散歩は、時間ではなく**地面の温度**で決まります。気温28度の日、アスファルトは50度を超えます。**犬の顔の高さは、人の顔の高さより暑い。**""",
                """留守番も同じで、上限の時間より先に決まるものがあります。**トイレと、温度と、その子の性格**です。""",
            ]},
            {"h": "食べない日は、数える", "p": [
                """「最近あまり食べない」では、病院でも判断できません。必要なのは、**何食ぶん抜けたか**という数字です。""",
                """食べない理由は山ほどありますが、**何食続いたか**は、そのどれを疑うかを分ける手がかりになります。数えていないと、そこから始められません。""",
            ]},
        ],
    },
    {
        "slug": "seasons", "cats": ["きせつ"],
        "title": "季節ごとに、気をつけること",
        "lead": "毎年同じことが起きるのに、毎年忘れます。前もって備えておくこと。",
        "intro": [
            "犬の1年は、人の1年より濃いです。夏の暑さ、冬の乾燥、春の予防シーズン。体が小さいぶん、外の環境がそのまま体にきます。",
            "やっかいなのは、**毎年同じことが起きるのに、毎年忘れる**ことです。去年どうしたかは、たいてい覚えていません。フィラリアをいつ始めていつ終えたか、去年の夏に何時に散歩していたか。",
            "ここでは、季節ごとに前もってやっておくことを書いています。時期は地域で大きく変わるので、目安として読んでください。",
        ],
        "sections": [
            {"h": "春に、まとめて出ていく", "p": [
                """4月から6月は、犬のお金がいちばん動く時期です。**狂犬病予防注射、混合ワクチン、フィラリアの検査と予防。**これが重なります。""",
                """**一度だけ、年間でいくらかかるかを数えておく**と、毎年慌てずに済みます。""",
            ]},
            {"h": "夏と冬は、足元で決まる", "p": [
                """夏は地面の温度、冬は乾燥と暖房。**どちらも、人の顔の高さでは分からないところで起きています。**""",
                """気温28度の日、アスファルトは50度を超えます。**手の甲を5秒あてられないなら、その時間は出ない。**それだけで防げるものがあります。""",
            ]},
        ],
    },
]


def hub_jsonld(hub, metas):
    d = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": hub["title"],
        "description": hub["lead"],
        "url": f'{BASE}/knowledge/{hub["slug"]}.html',
        "inLanguage": "ja",
        "isPartOf": {"@type": "WebSite", "name": "Wandary", "url": BASE},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(metas),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "url": f'{BASE}/knowledge/{m["slug"]}.html', "name": m["title"]}
                for i, m in enumerate(metas)
            ],
        },
    }
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>"


# まとめページを出す下限。1〜2本しか無いハブは中身が薄く、
# 検索にも拾われないうえ、読んだ人にも空振りになる
HUB_MIN = 3


def build_hubs(all_metas, head, foot):
    """クラスタごとのまとめページ。記事が HUB_MIN 本たまってから出す"""
    # 先に「どれを出すか」を決める。決まる前に書くと、
    # 「ほかのまとめ」がまだ無いページを指してしまう (404になる)
    made = [(h, [m for m in all_metas if m["cat"] in h["cats"]]) for h in HUBS]
    made = [(h, ms) for h, ms in made if len(ms) >= HUB_MIN]

    for hub, metas in made:
        intro = "\n  ".join(f"<p>{inline(t)}</p>" for t in hub["intro"])
        # ハブは「一覧の前置き」ではなく、**それ自体が記事**。
        # 導入だけだと1,000字に満たず、検索には拾われない。
        # sections に見出しごとの中身を書く (無ければ導入だけ)
        blocks = []
        for sec in hub.get("sections", []):
            blocks.append(f'  <h2>{html.escape(sec["h"])}</h2>')
            blocks.append(render_body("\n\n".join(sec["p"])))
        sections = "\n".join(blocks)
        items = "\n".join(
            f'    <li class="pick-item">\n'
            f'      <a href="{m["slug"]}.html">{html.escape(m["title"])}</a>\n'
            f'      <p>{html.escape(m["lead"])}</p>\n'
            f'    </li>'
            for m in metas
        )
        others = "\n".join(
            f'      <li><a href="{h["slug"]}.html">{html.escape(h["title"])}</a></li>'
            for h, _ in made if h["slug"] != hub["slug"]
        )
        page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(hub["title"])} | Wandary</title>
<meta name="description" content="{html.escape(hub["lead"], quote=True)}">
<link rel="canonical" href="{BASE}/knowledge/{hub["slug"]}.html">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(hub["title"], quote=True)}">
<meta property="og:description" content="{html.escape(hub["lead"], quote=True)}">
<meta property="og:url" content="{BASE}/knowledge/{hub["slug"]}.html">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
{hub_jsonld(hub, metas)}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
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
  <p class="article-date"><a href="./">よみもの</a></p>
  <h1 class="page-title">{html.escape(hub["title"])}</h1>
  <p class="article-lead">{inline(hub["lead"])}</p>

  {intro}
{sections}

  <h2>この{len(metas)}本</h2>
  <ul class="pick-list">
{items}
  </ul>

  {MED_NOTE}

  {AUTHOR}
  </div>

  <div class="related">
    <p class="related-label">ほかのまとめ</p>
    <ul class="pick-list">
{others}
    </ul>
  </div>

  <div class="app-cta">
    <span class="app-cta-label">Wandary</span>
    <span class="app-cta-title">気づいたことを、その場で残しておく</span>
    <p>ごはん・うんち・散歩・お薬・気になる様子をワンタップで残せる iOS アプリです。記録は自動で「経過ノート」にまとまり、動物病院でそのまま見せられます。</p>
    <div class="app-cta-actions">
      <a class="btn" href="{APP_URL}">App Store で見る</a>
      <span class="note">無料 · iPhone</span>
    </div>
  </div>
</main>
{foot}
</body>
</html>
'''
        (OUT / f'{hub["slug"]}.html').write_text(page)
    return [(h, len(ms)) for h, ms in made]


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
        toc, body_html = with_toc(render_body(m["body"]))
        page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(search_title(m))} | Wandary</title>
<meta name="description" content="{html.escape(search_description(m), quote=True)}">
<link rel="canonical" href="{BASE}/knowledge/{m["slug"]}.html">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Wandary">
<meta property="og:title" content="{html.escape(m["title"], quote=True)}">
<meta property="og:description" content="{html.escape(search_description(m), quote=True)}">
<meta property="article:published_time" content="{m["date"]}">
<meta property="article:modified_time" content="{m.get("updated", m["date"])}">
<meta property="article:section" content="{html.escape(m["cat"], quote=True)}">
<meta property="og:url" content="{BASE}/knowledge/{m["slug"]}.html">
<meta property="og:image" content="{BASE}/img/ogp.png">
<meta name="twitter:card" content="summary_large_image">
{jsonld(m)}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
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

{toc}
{body_html}

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
    hubs_made = build_hubs(metas, head, foot)
    hublinks = "\n".join(
        f'    <li class="pick-item">\n'
        f'      <a href="{h["slug"]}.html">{html.escape(h["title"])}</a>\n'
        f'      <p>{html.escape(h["lead"])} ({n}本)</p>\n'
        f'    </li>'
        for h, n in hubs_made
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/img/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
<link rel="stylesheet" href="../style.css">
</head>
<body>
{head}
<main>
  <div class="sheet">
  <h1 class="page-title">よみもの</h1>
  <p>犬と暮らすうえで知っておきたいことを、飼い主の目線でまとめています。
  数をそろえるより、一本ずつ書ききることを大事にしています。</p>

  <h2>テーマから読む</h2>
  <ul class="pick-list">
{hublinks}
  </ul>

  <h2>新しい順に読む</h2>
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
    live = {m["slug"] for m in metas} | {h["slug"] for h, _ in hubs_made}
    for f in OUT.glob("*.html"):
        if f.stem != "index" and f.stem not in live:
            f.unlink()
            print(f"  (取り下げ) {f.name}")

    print(f"記事 {len(metas)}本 + まとめ {len(hubs_made)}枚 + 一覧を書き出しました")
    for h, n in hubs_made:
        print(f'  まとめ  {h["slug"]}.html  {h["title"]} ({n}本)')
    for m in metas:
        print(f'  {m["date"]}  [{m["cat"]}]  {m["slug"]}.html  {m["title"]}')
    if waiting:
        print(f"\n公開待ち {len(waiting)}本 (その日が来たら自動で出ます)")
        for m in sorted(waiting, key=lambda m: m["date"]):
            print(f'  {m["date"]}  [{m["cat"]}]  {m["title"]}')


if __name__ == "__main__":
    build()
