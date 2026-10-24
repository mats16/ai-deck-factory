# Fonts

Open when choosing or changing the font of a theme (from `SKILL.md`, [create.md](create.md), or other skills).


Google Slides renders only Google Fonts. The Japanese fonts confirmed to render are `JP_FONTS` in `../deck-practices/scripts/brand.py` (on 2026-10-07, the same text was rendered in each font in a trial deck copied from the template).

| Impression of the original font | Google Fonts candidates with Japanese |
|---|---|
| Ordinary Gothic (Arial, Helvetica, Roboto, DM Sans, Inter, メイリオ, 游ゴシック, ヒラギノ角ゴ) | Noto Sans JP (default), IBM Plex Sans JP (companies that use IBM Plex), BIZ UDPGothic (companies that put readability first) |
| Geometric Gothic (Montserrat, Poppins, Futura) | Zen Kaku Gothic New, M PLUS 2, LINE Seed JP |
| Rounded Gothic | M PLUS Rounded 1c, Zen Maru Gothic |
| Mincho / serif (Times, Georgia, Garamond) | Noto Serif JP, Shippori Mincho, Zen Old Mincho, BIZ UDPMincho |

- `Noto Sans CJK JP`, `Hiragino Sans`, and `Yu Gothic` are accepted by the API but render as Mincho and a Latin serif (`NO_RENDER` in `template.py`). `Meiryo` rendered as a Gothic, but it could not be confirmed to be Meiryo itself (do not use it).
- `BIZ UDGothic` and `Kosugi Maru` have monospaced alphanumerics, so the spacing between letters looks wide.
- Whether a font rendered cannot be told from the API's values (it returns the specified name as is). Check the images of the sample pages.
- The only Latin font that can be written in `font` is DM Sans (`FONT_EM` in `../deck-practices/scripts/brand.py`). It has no Japanese glyphs, so Google Slides renders Japanese in another Gothic (rendered and checked on 2026-10-15: about 0.92 em per character, a little narrower than the assumed 1 em). `template.py audit` prints 「欧文（和文は別のゴシック。字幅を測ってあり、font に書ける）」.
- The width estimate in `slides.py` (`em_width`) assumes body alphanumerics at the `FONT_EM` width (Noto Sans JP's `ASCII_EM`, DM Sans's `DM_SANS_EM`; for bold, each Bold's `ASCII_BOLD_EM` and `DM_SANS_BOLD_EM`) and code at `MONO_EM` (Cascadia Mono). If another font is written in `font` or `mono`, it still estimates with the Noto Sans JP and Cascadia Mono widths, so the alphanumeric widths differ and the wrap estimates (build-time warnings, `d.card` height, lint's line counts) drift. Check the images of the sample pages and of the built material.
- The default monospace font for code is Cascadia Mono. The theme's `mono` changes it (in the slide and document theme files: `themes/slides/<name>.json` and `themes/docs/<name>.json`). Monospace text carries no Japanese, so it is not limited to `JP_FONTS`, but fonts with ligatures (`LIGATURE_MONO` in `../deck-practices/scripts/brand.py`: JetBrains Mono, Fira Code, Cascadia Code) are rejected (`../slides-build/visual.md` §2). A name not in Google Fonts is accepted by the API and silently rendered in another font (Arial). After writing it, rebuild the sample pages with `template.py <name>` and check in the `gslides.py check` images that code renders monospaced and that `->` has not turned into a single arrow glyph.
- The list of checked fonts is in 「書体」 of the repository README.
