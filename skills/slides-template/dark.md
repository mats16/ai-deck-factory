# Dark body themes

Open from `SKILL.md` or [create.md](create.md) when the body-page background (`BG`) is dark.


A theme that makes even the body-page background (`BG`) dark (light text on a black background, like the website of a space or AI company). The roles are the same as in a light theme, but the colors assigned are reversed. Roles that a light theme covers with one color are split using the roles written by name (`HEAD`, `CARD`, `SUB_ON_NAVY`, `ON_RED`).

| Role | Color to assign (guide) |
|---|---|
| `BG` | Body background. Black or a very dark gray |
| `NAVY` | Background of the cover and dividers, and of the conclusion band, table header rows, and code boxes. If it equals `BG`, the conclusion band cannot be seen, so use a gray one step lighter than `BG` (about `1A1A1A` if `BG` is `000000`). The cover and dividers also take this color |
| `PANEL`, `NAVY_BLOCK` | Panels and the blocks inside the divider. `PANEL` may equal `NAVY`. `NAVY_BLOCK` sits on the divider background (`NAVY`), so make it lighter than `NAVY` |
| `CARD` | Background of cards and table cells. About as dark as `BG` (enclosed by the `RULE` border) |
| `HEAD`, `TEXT`, `SUB` | Headings, body text, and secondary text. From a near-white color, progressively darker grays |
| `RULE` | Card borders and rules. A dark gray (a light one makes the borders stand out) |
| `SUB_ON_NAVY` | Notes on navy, and the footer of the cover and dividers. Because `RULE` is dark, write a light gray separately |
| `RED`, `RED_TEXT`, `RED_ON_NAVY` | Emphasis color. On a dark background, all three can often be the same light color |
| `ON_RED` | Text on a `RED` fill (number circles). If white does not reach the standard on a light emphasis color (white on orange `FF6308` is 2.98:1), black |
| `RED_SOFT`, `STAGE_TEXT`, `DECOR` | Background of small red tags: the emphasis color made very dark. Tag text: black. Chapter number: a gray that reaches 3:1 against the divider background (`NAVY`; also `BG` if there is a divider with a white background) (slides-visual-038) |

- Where to write the colors, how to measure them, and how to create the template are the same as for light themes (steps 5–8 of the flow). `slides.py lint` measures the same role pairs (`HEAD`, `TEXT`, `SUB`, and `RED_TEXT` on the body, panels, and cards; `WHITE` and `SUB_ON_NAVY` on navy; `ON_RED` on `RED`; and so on).
- The difference between the background and the panels or conclusion band is outside the text standard, and lint does not measure it. Dark colors look close to each other (`000000` and `1A1A1A` are 1.2:1), so check in the sample images whether the boundaries between surfaces can be seen.
- lint and `box_pad.py` tell covers and dividers apart not by background color but by whether `slides.py` built the page with a `NAVY` background. They tell cards apart by the theme's `CARD` color. If `PANEL` has the same value as `NAVY`, a panel that spans the full body width down to the bottom of the page (6.60 in) is counted as a conclusion band, and code-like lines inside the panel are required to be monospace.
- Materials whose page JSON (pages.py) writes heading text as `NAVY` and card backgrounds as `WHITE` become unreadable in a dark theme (write `HEAD` and `CARD`; `../slides-build/visual.md` §1). They appear in lint's contrast list.
