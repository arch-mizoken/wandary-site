#!/usr/bin/env python3
"""測定IDを入れて、プライバシーポリシーに追記する。**同時に、1回で。**

    python3 tools/enable_ga.py G-XXXXXXXXXX     # 入れる
    python3 tools/enable_ga.py --off            # 外す

**なぜ1つのコマンドにしてあるか。**
計測を始めるのと、それを公表するのは、片方だけ出てはいけない組み合わせです。

- 動かしてから書く → 公表していない送信が起きる（外部送信規律）
- 書いてから動かす → 使っていないものを「使っている」と書いた状態になる

どちらも避けたいので、**ga.js とポリシーを同じ1回で書き換えます。**
`check_links.py` が、片方だけになっていないかを見張ります。

入れたあとにやること:

    python3 tools/build_articles.py && python3 tools/build_goods.py
    python3 tools/sitemap.py && python3 tools/check_links.py
"""
import pathlib, re, sys, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
GA = ROOT / "ga.js"
POLICY = ROOT / "privacy.html"

SERVICE = ('    <li>Google アナリティクス（<strong>ウェブサイトのみ</strong>のアクセス解析）'
           '— <a href="https://policies.google.com/privacy?hl=ja" target="_blank" rel="noopener">'
           'Google プライバシーポリシー</a> / '
           '<a href="https://policies.google.com/technologies/partner-sites?hl=ja" '
           'target="_blank" rel="noopener">Google によるデータの使用</a></li>\n')

SERVICE_ANCHOR = ('    <li>Cloudflare Workers / D1（ウェブサイト上のアンケート・'
                  'ご意見フォームの受け口）— <a href="https://www.cloudflare.com/ja-jp/privacypolicy/"'
                  ' target="_blank" rel="noopener">Cloudflare プライバシーポリシー</a></li>\n')

PLAIN = '''  <h2>5. 分析ツール・広告について</h2>
  <p>本アプリは、アクセス解析ツールおよび広告配信サービスを利用していません。</p>'''

WITH_GA = '''  <h2>5. 分析ツール・広告について</h2>
  <h3>アプリ</h3>
  <p><strong>本アプリは、アクセス解析ツールおよび広告配信サービスを利用していません。</strong>記録データや写真、端末の情報が開発者や第三者に送信されることはありません。</p>

  <h3>ウェブサイト（wandary.jp）</h3>
  <p>ウェブサイトでは、どのページが読まれているかを知るために <strong>Google アナリティクス 4</strong> を利用しています。閲覧されたページ、参照元（どこから来たか）、おおよその地域、ブラウザの種類などが Google に送信されます。この計測には Cookie を使用します。</p>
  <p><strong>氏名やメールアドレスなど、個人を特定する情報は送信しません。</strong>また、<strong>IPアドレスは Google アナリティクス 4 では記録・保存されません</strong>（おおよその地域を推定したあと破棄されます）。アプリ内の記録データが、ウェブサイトの計測に使われることもありません。</p>
  <p>計測を望まれない場合は、Google が提供する <a href="https://tools.google.com/dlpage/gaoptout?hl=ja" target="_blank" rel="noopener">アナリティクス オプトアウト アドオン</a> をブラウザに追加するか、ブラウザの設定で Cookie を無効にしてください。<strong>いずれの場合も、サイトの閲覧やアプリの利用に支障はありません。</strong></p>
  <p>広告配信サービスは、アプリ・ウェブサイトのいずれでも利用していません。</p>'''

FOUNDED = '  <p class="date">制定日: 2026年7月22日</p>'


def set_id(value):
    s = GA.read_text()
    s2 = re.sub(r"^var WANDARY_GA = '[^']*';", f"var WANDARY_GA = '{value}';", s, count=1, flags=re.M)
    if s2 == s and value:
        raise SystemExit("ga.js の WANDARY_GA の行が見つかりません")
    GA.write_text(s2)


def on(ga_id):
    if not re.fullmatch(r"G-[A-Z0-9]{6,12}", ga_id):
        raise SystemExit(f"測定IDの形が違います: {ga_id}（G- で始まる英大文字と数字）")
    s = POLICY.read_text()
    if "Google アナリティクス" in s:
        raise SystemExit("プライバシーポリシーには、すでに書いてあります")
    if PLAIN not in s or SERVICE_ANCHOR not in s or FOUNDED not in s:
        raise SystemExit("privacy.html の形が変わっています。手で直してください")
    today = datetime.date.today()
    s = s.replace(SERVICE_ANCHOR, SERVICE_ANCHOR + SERVICE, 1)
    s = s.replace(PLAIN, WITH_GA, 1)
    s = s.replace(FOUNDED, '  <p class="date">制定日: 2026年7月22日<br>'
                  f'改定日: {today.year}年{today.month}月{today.day}日'
                  '（ウェブサイトのアクセス解析について追記）</p>', 1)
    POLICY.write_text(s)
    set_id(ga_id)
    print(f"測定ID {ga_id} を入れて、ポリシーに追記しました。")
    print("build_articles.py / build_goods.py / sitemap.py / check_links.py を続けて実行してください。")


def off():
    s = POLICY.read_text()
    if "Google アナリティクス" in s:
        s = s.replace(SERVICE, "", 1).replace(WITH_GA, PLAIN, 1)
        s = re.sub(r'<br>\n?改定日: .*?（ウェブサイトのアクセス解析について追記）', "", s, count=1)
        POLICY.write_text(s)
    set_id("")
    print("測定IDを空にして、ポリシーの追記も消しました。")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    off() if sys.argv[1] == "--off" else on(sys.argv[1])
