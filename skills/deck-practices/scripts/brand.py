#!/usr/bin/env python3
"""スライド（slides.py）とドキュメント（docs.py）で同じ、見た目の共通の値: 書体と字幅の表、色の既定、会社の著作権表示とロゴ（factory.toml の [brand]）、
使い回す画像（asset）。どちらのテーマのファイルの font・mono も、ここの theme_font・theme_mono で確かめる。標準ライブラリだけ。
usage: python3 brand.py --selftest"""
import os, re, sys, tomllib
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapi  # noqa: E402

# ---- 書体（../../slides-build/visual.md の 2） ----
FONT = "Noto Sans JP"  # Google Fonts の名前。Noto Sans CJK JP と字形・文字幅は同じ（Google Fonts にない書体は黙って別の書体になる）
# Google Slides で描けることを確かめた、和文のある Google Fonts（2026-10-07。../../slides-template/fonts.md）。会社のテーマの書体はここから選ぶ
JP_FONTS = {FONT, "Noto Serif JP", "BIZ UDPGothic", "BIZ UDGothic", "BIZ UDPMincho", "M PLUS 1p", "M PLUS 2", "M PLUS Rounded 1c", "Zen Kaku Gothic New",
            "Zen Maru Gothic", "Sawarabi Gothic", "Kosugi Maru", "IBM Plex Sans JP", "LINE Seed JP", "Murecho", "Shippori Mincho", "Zen Old Mincho", "Klee One"}
MONO_DEFAULT = "Cascadia Mono"  # コードの箱・コマンドの等幅の書体の既定（Google Fonts。Windows Terminal の既定でリガチャがない。visual.md の 2）。和文の字形がないので、ASCII の続きにだけ付ける（mono_reqs）
LIGATURE_MONO = {"JetBrains Mono", "Fira Code", "Cascadia Code"}  # Google Fonts の版にリガチャがあり、Google Slides が描く（2026-10-09。visual.md の 2）。テーマの mono に書けない

# [deck-brand-003] 英数字と記号の幅（em）。Noto Sans CJK JP Regular の実測（2026-10-08）。前は英数字を一律 0.57 にしていて、大文字の多い行を
# 2.52 in と見込み、2.56 in の枠に収まるとしたが、実際は 2.57 in で Google が最後の 1 字を折り返した
ASCII_EM = dict(zip(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~", (
    .22, .32, .47, .56, .56, .92, .68, .28, .34, .34, .47, .56, .28, .35, .28, .39, .56, .56, .56, .56, .56, .56, .56, .56, .56, .56, .28, .28, .56, .56,
    .56, .47, .95, .61, .66, .64, .69, .59, .55, .69, .73, .29, .54, .65, .54, .81, .72, .74, .63, .74, .64, .60, .60, .72, .57, .88, .57, .53, .60, .34,
    .39, .34, .56, .56, .61, .56, .62, .51, .62, .55, .33, .56, .61, .28, .28, .55, .28, .93, .61, .61, .62, .62, .39, .47, .38, .61, .52, .80, .50, .52,
    .47, .34, .27, .34, .56)))
# DM Sans の英数字と記号の幅（em）。Google Fonts の版（opsz・wght の可変）の opsz 14・wght 400 の hmtx。Google Slides は字の大きさによらずこの版で描く
# （2026-10-15 に 12・18・30pt で描いて測り、見込みとのずれは 1% 以内。opsz 9 の既定の値では「1」が 1 割広い）。和文の字はなく、Google が別のゴシックで描く（1 字 0.92 em ほど。1 で見込む）
DM_SANS_EM = dict(zip(ASCII_EM, (
    .27, .25, .29, .80, .58, .79, .73, .16, .37, .37, .48, .55, .18, .54, .20, .39, .68, .31, .58, .59, .61, .61, .63, .53, .61, .63, .20, .23, .55, .55,
    .55, .52, 1.00, .66, .60, .72, .69, .56, .54, .76, .68, .23, .50, .58, .53, .84, .69, .77, .58, .77, .59, .58, .56, .66, .67, .97, .60, .58, .54, .31,
    .39, .31, .62, .66, .21, .54, .63, .57, .63, .57, .34, .56, .57, .24, .24, .50, .22, .89, .57, .59, .63, .63, .37, .50, .39, .57, .53, .76, .50, .56,
    .46, .43, .23, .43, .55)))
# 太字の英数字と記号の幅（em）。Noto Sans CJK JP Bold と、DM Sans の opsz 14・wght 700 の hmtx（2026-10-19）。Regular より 6〜7% 広く、Regular の幅で見込むと、
# 2.3 in のカードの見出し「kuromoji（Java）」（太字 12pt）を 1.40 in で 1 行と見たが、実際は 1.47 in で 1.44 in の枠から折り返し、本文に重なった
ASCII_BOLD_EM = dict(zip(ASCII_EM, (
    .23, .37, .57, .59, .59, .96, .74, .33, .38, .38, .51, .59, .33, .37, .33, .39, .59, .59, .59, .59, .59, .59, .59, .59, .59, .59, .33, .33, .59, .59,
    .59, .51, 1.01, .64, .68, .66, .71, .61, .58, .72, .76, .33, .57, .69, .58, .85, .75, .77, .67, .77, .68, .62, .62, .75, .62, .92, .63, .58, .61, .38,
    .39, .38, .59, .57, .63, .59, .64, .53, .64, .58, .37, .60, .64, .30, .31, .60, .32, .96, .64, .63, .64, .64, .44, .49, .42, .64, .58, .86, .56, .57,
    .51, .38, .30, .38, .59)))
DM_SANS_BOLD_EM = dict(zip(ASCII_EM, (
    .23, .31, .37, .86, .60, .90, .78, .20, .41, .41, .51, .58, .25, .58, .25, .43, .70, .36, .58, .60, .65, .62, .63, .54, .63, .64, .25, .28, .58, .58,
    .58, .54, 1.05, .71, .64, .74, .71, .58, .56, .78, .71, .27, .54, .65, .56, .89, .73, .78, .61, .78, .63, .60, .60, .69, .71, 1.02, .67, .64, .58, .38,
    .43, .38, .68, .72, .23, .59, .66, .61, .66, .60, .37, .60, .62, .27, .27, .58, .27, .94, .62, .61, .66, .66, .41, .53, .43, .62, .56, .82, .57, .60,
    .49, .47, .27, .47, .58)))
FONT_EM = {FONT: (ASCII_EM, ASCII_BOLD_EM), "DM Sans": (DM_SANS_EM, DM_SANS_BOLD_EM)}  # 英数字の幅を測った書体（Regular, Bold）。テーマの font には、JP_FONTS とこれが書ける。ほかの JP_FONTS は Noto Sans JP の幅で見込む

# ---- 色の既定。テーマのファイルの colors に同じ名前で書くと替わる（slides.py の FIXED、docs.py の load_theme） ----
WHITE = "FFFFFF"
TEXT, RULE = "303F47", "DCE0E2"  # 本文／罫線（スライドでは濃紺の上の補足も）


# ---- 会社の著作権表示とロゴ ----
def _brand():
    """factory.toml の [brand]（社名と著作権表示。../../slides-template/create.md）。import のときに読むので gapi.locate で探し、gapi の覚えた結果を作らない。
    書き方の誤りでは止めない（factory() を呼ぶところと factory-doctor が止める）。"""
    try:
        return tomllib.loads(p.read_text()).get("brand", {}) if (p := gapi.locate()) else {}
    except tomllib.TOMLDecodeError:
        return {}


_BRAND = _brand()
COMPANY = _BRAND.get("company", "")  # 表紙の左下。空なら置かない
PLACEHOLDER_COPYRIGHT = "© 2026 Example, Inc. All rights reserved."  # [brand] copyright を書いていないときの仮の値。これと空のときは組めない（need_brand）
BRAND_COPYRIGHT = _BRAND.get("copyright", PLACEHOLDER_COPYRIGHT)  # 初公表年。既存資料の年を現在年へ自動更新しない
LOGO = _BRAND.get("logo")  # ドキュメントの表紙のロゴ（assets/ の中のパスか URL）。なければ置かない
COPYRIGHT_PT = 9  # 著作権表示と、高さをそろえるページ番号だけは 11pt 以上の例外。本文を邪魔しない（2026-10-08、ページ番号は 2026-10-13）
COPYRIGHT_FOOTER = re.compile(r"^©\s*\d{4}\s+.+?\s+All rights reserved\.(?:\s*｜\s*(?:Internal Only|Confidential))?\s*$", re.I)


def need_brand(copyright=BRAND_COPYRIGHT):
    """著作権表示 copyright（[brand] の値。スライドはテーマの copyright があればそれを渡す）がなければ止める。仮の著作権表示を全ページに書いた資料を出さないため
    （lint は形しか見ないので、仮の値も通る）。スライド・ドキュメント・テンプレートを組む build が、Slides・Docs に送る前に呼ぶ。"""
    if copyright.strip() in ("", PLACEHOLDER_COPYRIGHT):  # 空（copyright = ""）と、前後に空白を付けた仮の値も、書いていないのと同じ（doctor と同じ判定）
        sys.exit("factory.toml の [brand]（テーマごとに変えるなら、テーマのファイルの copyright）に copyright（例: copyright = \"© 2026 Acme, Inc. All rights reserved.\"）を書いてから組む。"
                 "書かないと全ページの左下が仮の表示（Example, Inc.）になる")


def theme_font(t):
    """テーマの表 t（スライドのテーマ・[docs.themes]）の本文の書体。書いていなければ FONT。和文を描けると確かめた書体（JP_FONTS）か、英数字の幅を測った
    欧文の書体（FONT_EM の DM Sans。和文は Google が別のゴシックで描く）でなければ止める（ほかの書体は、和文が別の書体になるか、描けない。deck_font も FONT に戻す）。"""
    if not isinstance(f := t.get("font", FONT), str) or f not in JP_FONTS | set(FONT_EM):
        sys.exit(f"テーマの font {f!r} は、和文を描けると確かめた書体（slides.py の JP_FONTS）にも、字幅を測った欧文の書体（FONT_EM）にもない。slides-template の fonts.md から選ぶ")
    return f


def theme_mono(t):
    """テーマの表 t（スライドのテーマ・[docs.themes]）の等幅の書体。書いていなければ MONO_DEFAULT。和文を載せないので JP_FONTS には限らない（Google Fonts にない書体は黙って別の書体になる）。"""
    if not isinstance(m := t.get("mono", MONO_DEFAULT), str) or not m.strip():
        sys.exit(f"テーマの mono {m!r} は書体の名前でない（例: Cascadia Mono）")
    if " ".join(m.split()).casefold() in {x.casefold() for x in LIGATURE_MONO}:  # 大文字と小文字、空白の数の違いでも同じ書体とみなす
        sys.exit(f"テーマの mono {m!r} は、Google が描くとリガチャが出る（-> が矢印 1 字になる。visual.md の 2）。リガチャのない書体にする")
    return m.strip()


ASSETS = Path(__file__).resolve().parents[2] / "slides-build" / "assets"  # プラグインの使い回す画像（出どころは slides-build/assets/README.md）


def asset(path):
    """使い回す画像のパス。ワークスペースの assets/ にあればそれを、なければプラグインの ASSETS を使う。"""
    dirs = (gapi.factory_path().parent / "assets", ASSETS)
    for d in dirs:
        if (d / path).is_file():
            return str(d / path)
    sys.exit(f"assets にない: {path}（{'、'.join(map(str, dirs))} を見た）")


def selftest():
    assert COPYRIGHT_FOOTER.match("© 2026 Acme, Inc. All rights reserved.｜Internal Only") and not COPYRIGHT_FOOTER.match("© Acme 2026")
    assert theme_font({}) == FONT and theme_font({"font": "DM Sans"}) == "DM Sans" and theme_mono({"mono": " IBM Plex Mono "}) == "IBM Plex Mono"
    for bad in (lambda: theme_font({"font": "Arial"}), lambda: theme_mono({"mono": "fira  code"}), lambda: need_brand(PLACEHOLDER_COPYRIGHT + " "), lambda: need_brand("")):
        try:
            bad()
            raise AssertionError("止めなかった")
        except SystemExit:
            pass
    need_brand("© 2026 Acme, Inc. All rights reserved.")
    assert set(FONT_EM) <= JP_FONTS | {"DM Sans"} and FONT_EM[FONT][0]["W"] == .88
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else __doc__)
