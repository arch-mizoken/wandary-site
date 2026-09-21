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
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {"_articles", "_goods", "_drafts", "tools", ".git"}

def targets(href):
    """そのURLが、どのファイルに当たるか"""
    path = href.split("#")[0].split("?")[0]
    if not path or path == "/":
        return ROOT / "index.html"
    if path.endswith("/"):
        return ROOT / (path.lstrip("/") + "index.html")
    return ROOT / path.lstrip("/")

def main():
    broken = []
    pages = [p for p in ROOT.rglob("*.html")
             if not any(part in SKIP_DIRS or part.startswith(".") for part in p.parts)]
    for page in sorted(pages):
        s = page.read_text(encoding="utf-8")
        for href in sorted(set(re.findall(r'(?:href|src)="(/[^"]*)"', s))):
            if not targets(href).exists():
                broken.append((page.relative_to(ROOT), href))

    if not broken:
        print(f"内部リンク: {len(pages)} ページ、切れているものはありません")
        return 0

    print("行き先が無いリンク:")
    for page, href in broken:
        print(f"  {page}  →  {href}")
    print("\n公開日がまだ先の記事を指していないか確かめること "
          "(_articles/*.md の date)。")
    return 1

if __name__ == "__main__":
    sys.exit(main())
