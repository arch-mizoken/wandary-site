#!/usr/bin/env python3
"""記事の本文に、書きかけの跡が残っていないか見る。

    python3 tools/check_text.py

見つけたのは、こういうもの:

  - 「預ける」が「предける」になっていた（キリル文字が混ざった）
  - 「心当たり」が「possibility」のまま残っていた（英単語が残った）

どちらも**読み返しても気づけません。**日本語の中に埋まっていると、
目が滑ります。だから機械に見させる。

単位 (kg, ml, kcal) と、よく使う略語 (PDF, CSV, SNS…) は見逃す。
新しく許すものが出たら ALLOW に足すこと。
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_articles"

# 単位と略語。ここに無い英単語は、書きかけとみなす
ALLOW = {
    "kg", "g", "mg", "ml", "l", "kcal", "cm", "mm", "m", "km",
    "pdf", "csv", "sns", "line", "ok", "ng", "cbc", "id",
    "apple", "google", "icloud", "wandary", "x", "ai", "u",
}

WORD = re.compile(r"(?<![A-Za-z/.-])[A-Za-z]{1,}(?![A-Za-z/.-])")
OTHER_SCRIPT = re.compile(r"[Ѐ-ӿͰ-Ͽ]")


def main():
    bad = []
    for p in sorted(SRC.glob("*.md")):
        text = p.read_text()
        head, body = text.split("\n---\n", 1)
        for i, line in enumerate(body.splitlines(), 1):
            if "](http" in line:          # リンクのURLは見ない
                continue
            for m in WORD.finditer(line):
                if m.group(0).lower() not in ALLOW:
                    bad.append((p.stem, i, m.group(0), line.strip()))
            for m in OTHER_SCRIPT.finditer(line):
                bad.append((p.stem, i, m.group(0), line.strip()))

    if not bad:
        print(f"本文: {len(list(SRC.glob('*.md')))} 本、書きかけの跡はありません")
        return 0

    print("日本語でない文字が残っています:")
    for slug, i, found, line in bad:
        print(f"  {slug}:{i}  「{found}」")
        print(f"      {line[:70]}")
    print("\n単位や略語なら、tools/check_text.py の ALLOW に足してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
