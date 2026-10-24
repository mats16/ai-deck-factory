# Ledger of image assets

This file collects where the images, icons, and logos pasted into slides and documents come from. The rules for pasting them (which to use first, how to use `d.image`, `d.icon`, `png()`, and `asset()`) are in `../images.md`. The research history and the results of the URLs we tried are in `Research/google_slides_public_image_urls_20261008.md`.

- [slides-image-001] **Use what can be pasted as a URL first.** The Slides API reads only PNG, JPG, and GIF by URL. Turn SVG into a PNG URL with `png(<SVG URL>)` (wsrv.nl).
- [slides-image-002] **Put in this folder only what is distributed only as files.** Do not copy them into the material folder's `build/assets/`; point to them with `asset("gcp/bigquery.png")`. Images for only that material (screenshots, figures from the deck being reused) stay in `build/assets/` as before.
- When you add one, name it with lowercase English letters, digits, and hyphens (`<product>.png`), and add one line to "Files in this folder" below (the source URL, the date you got it, the allowed use, and whether it can go outside the company). If both PNG and SVG are distributed, put both.
- Logos and icons are trademarks of each company. Use them in architecture diagrams and explanations; do not distort them, do not change their colors, and do not make them look like our own (each company's terms are in the tables below).

## Pasting by URL

Forms we confirmed on 2026-10-08 can be pasted with the Slides API. Sizes are in px.

| Use | URL form | Size | Allowed use |
|---|---|---|---|
| Line icons and product logos (Iconify) | `{"type": "icon", "name": "<set>:<name>"}` in JSON (internally, `https://api.iconify.design/<set>/<name>.svg?color=…` goes through `png()`). Sets: `tabler` (line icons. Default), `material-symbols`, `simple-icons` (one-color logos), `logos` (color logos. `logos:<name>` sometimes includes the company name as text; for the mark only use `logos:<name>-icon` (example: `logos:databricks-icon`). `logos:aws`, `logos:google-cloud`, `logos:microsoft-azure`, `logos:snowflake-icon`, `logos:oracle`, `logos:salesforce`, `logos:tableau-icon`, `logos:microsoft-power-bi`, `logos:aws-redshift`, and so on). Find names at https://icon-sets.iconify.design/ | 512 (can be set) | Per set (tabler MIT, material-symbols Apache-2.0, simple-icons and logos CC0). Logo trademarks are separate |
| Images available only as SVG (such as customer logos) | `png("<SVG URL>", w=1024)` → `https://wsrv.nl/?url=…&output=png&w=1024` | As specified | The original image's terms |
| Architecture diagram icons for AWS, Azure, Kubernetes, and OSS (mingrammer/diagrams) | `https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/<aws, azure, k8s, onprem, saas, and so on>/<category>/<name>.png`. The list is at https://github.com/mingrammer/diagrams/tree/master/resources | 256–300 | Code is MIT. The art follows each company's terms: [AWS](https://aws.amazon.com/architecture/icons/) (may be used in architecture diagrams, materials, and presentations), [Azure](https://learn.microsoft.com/en-us/azure/architecture/icons/) (may be used in architecture diagrams, training, and documents. Do not distort) |
| AWS icons (AWS Labs) | `https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v23.1/dist/<category>/<name>.png` | 64 | The art is CC-BY-ND 2.0. Small, so up to 0.5 in |
| Photos (Unsplash) | `https://images.unsplash.com/photo-<ID>?w=1600&fm=jpg` | As specified | Unsplash License (commercial use allowed, credit optional) |
| SVG logos (Wikimedia Commons) | `https://upload.wikimedia.org/wikipedia/commons/thumb/<a>/<ab>/<file>.svg/<width>px-<file>.svg.png`. Width must be one of 20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840 | As specified | Per file |
| Google product icons | `https://www.gstatic.com/images/branding/product/2x/<slides, sheets, drive>_2020q4_48dp.png`, `google_cloud_48dp.png`, `gemini_48dp.png` | 96 | Google's brand guidelines. There is no official list, and they may change |
| [slides-image-003] The pi (pi coding agent) mark | `png("https://pi.dev/favicon.svg")`. One color, black (`#111111`), so place it on a white card | 1024 | Not stated. The mark of the official pi.dev site. Use it as the logo in a product box |
| [slides-image-004] The T3 Code mark | `https://raw.githubusercontent.com/pingdotgg/t3code/main/assets/prod/black-universal-1024.png` (a white T3 on a black rounded square) | 1024 | The repository is MIT. Trademark terms for the mark are not stated. Use it as the logo in a product box |
| Emoji (Fluent Emoji, Microsoft) | `https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/<name>/3D/<name>_3d.png` | 256 | MIT |

Do not use:

- `gcp/` in mingrammer/diagrams (old artwork. Google asks people not to use it from 2026) and `onprem/analytics/databricks.png` (old logo). For Google Cloud, use the files in this folder.
- Assets that require credit (Icons8, Twemoji, the animated Noto Emoji). Others are enough.
- Services that make diagrams from URLs (mermaid.ink, kroki.io, quickchart.io). The diagram content goes to a third party, so do not give them customer information. Build slide diagrams from tables and shapes (pages.md "Laying out shapes and text"). For mermaid diagrams in documents, `docs.py` draws them with the local mermaid-cli (docs-write-009 in `../../docs-build/SKILL.md`).

## Files in this folder

| Folder | Content | Source | Date obtained | Allowed use, and whether it can go outside the company |
|---|---|---|---|---|
| `blank.pptx` | The blank file used when `template.py --from-base` is not given a source URL (`../themes.md`). 13.33 × 7.5 in (12188952 × 6858000 EMU); the only layout is Blank (with only a page number frame); the master has `<p:hf hdr="0" ftr="0" dt="0"/>` (the setting that shows slide numbers); one slide with a page number frame (without it, Google Slides turns slide numbers off and added pages get no frame); `lIns`, `tIns`, `rIns`, and `bIns` of `a:bodyPr` in the page number frames of the master, Blank, and the slide are 0 (`template.py` assumes inner padding of 0). `template.py --selftest` checks these 5 things | Made from python-pptx's default pptx by deleting the other layouts and the date and footer frames, and removing the author, printer settings, and thumbnail. After conversion, the master is named 「Office Theme」 | 2026-10-14 | Can go outside the company (the content is empty) |
| `gcp/` | Icons of the main Google Cloud products (4 colors, 512 px PNG and SVG). 22 of them, including `bigquery`, `cloud-storage`, `vertex-ai`, `looker`, `gke`, `cloud-run` | Core product icons from [Google Cloud icons](https://cloud.google.com/icons) (https://services.google.com/fh/files/misc/core-products-icons.zip) | 2026-10-08 | May be used in architecture diagrams and technical documents. Do not make it look like Google endorses it ([Brand Resource Center](https://about.google/brand-resource-center/guidance/)). Can go outside the company |
| `gcp/category/` | Category icons (2 colors) for products other than the main ones. 27 of them, including `data-analytics`, `databases`, `ai-machine-learning`, `storage` | Product category icons from the same page (https://services.google.com/fh/files/misc/category-icons.zip). The mapping of products to icons is at https://services.google.com/fh/files/misc/google-cloud-product-icons.pdf | 2026-10-08 | Same as above |
