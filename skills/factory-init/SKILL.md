---
name: factory-init
description: Create an AI Deck Factory workspace (the folder that holds materials and rules). Places templates of AGENTS.md, CLAUDE.md, factory.toml, references_index.md, rules/, and .gitignore, plus Customers/, Internal/, and Research/ (never overwrites existing files), fills in factory.toml with the user, and checks with factory-doctor. Use when asked 「ワークスペースを作って」, 「setup して」, or 「AI Deck Factory を使い始めたい」.
---

# Create a workspace

A workspace is the folder that holds the material folders and `factory.toml` (for example `~/Documents`). Scripts walk up from the current folder and treat the folder of the first `factory.toml` they find as the workspace. What goes in it, and the rule priority (the workspace AGENTS.md and `rules/` take priority over the plugin), are written in the placed `AGENTS.md`.

## Steps

When installing through a conversation (the repository's `INSTALL.md`), step 1 is already done. A conversation that just installed the plugin has not loaded this skill or any other skill, so for other skills (slides-build, slides-template, factory-doctor), open `skills/<skill>/SKILL.md` in the install location and follow it.

1. **Decide the location.** If not told, ask whether the current folder is fine. If the folder already has `factory.toml` or `AGENTS.md`, tell the user (do not overwrite; place only what is missing).
2. **Place the files.**
   ```sh
   python3 <this skill's folder>/scripts/init.py <workspace>
   ```
   Relay the 「置いた」 and 「残した」 lines of the output as they are.
3. **Fill in `factory.toml`.** Ask one item at a time and write it. Leave unknown items empty; they stay as `要確認` in doctor.
   - `[user] profile`: a file with the user's name, role, and customers in charge.
   - `[google]`: how to get a token. If gcloud is available, have the user run the `gcloud auth application-default login --scopes=…` that doctor prints, once (the user runs it themselves; a browser opens). If another mechanism gets the token, pass it in the environment variable `GOOGLE_OAUTH_ACCESS_TOKEN`. With gcloud's default OAuth client, `quota_project` is also required.
   - `[brand]`: `copyright` (the copyright notice at the bottom left of every page, in the form 「© <年> <社名> All rights reserved.」) is required. Without it, slides, documents, and templates cannot be built. `company` (the company name at the bottom left of the cover) and `logo` (the logo on the document cover; a path inside `assets/` or a URL) are optional.
   - `[drive] shared_themes`: the URL of the company-wide shared theme folder (where an administrator distributes templates). Leave it empty if the company does not distribute one. Once it is written, after `[drive] factory` and Google authentication, run `python3 <slides-build folder>/scripts/slides.py themes`, have the user choose which of the themes marked 「共有。」 to use, and run `python3 <slides-build folder>/scripts/slides.py theme <printed URL>` (copies the theme file `themes/slides/<name>.json` and writes the URL into `[slides.templates]`). If the shared themes are enough, the `--from-base` step below is not needed.
   - `[slides.templates]`: after filling `[drive] factory`, create templates with `python3 <slides-build folder>/scripts/template.py visual --from-base` (also `company` for company colors). If the user names a template to base it on, pass its URL as `--from-base <base URL>` (it is not kept in `factory.toml`; without it, the template is built from a blank pptx 〔`slides-build/assets/blank.pptx`〕) (created in Themes under `[drive] factory`). The URL is written into `[slides.templates]`. The colors and descriptions of visual and company are in the plugin's built-in theme files. To use the company's own template, create it with the skill `slides-template` (`[brand]` and the workspace theme file `themes/slides/<name>.json`. If more than one theme is used, have the user write a `description` for each 〔which materials and audience it is for〕).
   - `[slides] default_theme`: once the two items above have produced templates, ask for the default theme as a multiple-choice question (`slides-template`'s "Choosing the default theme").
   - `[drive]`: the root locations for customer-facing and internal slides and documents.
   - `[review]`: do not ask. Keep the template defaults (the outline review is done by AI; `/deck-review` runs up to 3 rounds). Change only when the user says so.
   - `[feedback.google_comments] watch_hours`: how long to watch comments after delivering a material. When installing through a conversation, write the value asked in step 1 of `INSTALL.md`. Otherwise do not ask; keep the template's 0 (no watching), and change only when the user says so.
   - `[sources]`: tools for gathering material (internal search, chat, meeting records, wiki, customer ledger, spend). Offer candidates from the MCP servers and skills in your own tool list and ask. To make per-tool usage a rule, write it in `rules/deck-practices/materials.md`.
4. **Adjust `AGENTS.md`.** Add the user's customers to the 「顧客とフォルダ」 table. Ask whether to create a profile for each added customer now; if yes, create it with the skill `customer-profile` (after filling `[sources]`). For template rules that do not fit, ask the user before changing them (workspace rules take priority, so changes here take effect).
5. **Ask whether to use git.** To keep a history of growing rules and checks, run `git init` in the workspace and make the first commit (the placed `.gitignore` includes only rules and settings). The user decides whether to push to a remote.
6. **Check.** Run the skill `factory-doctor` and fix until there are 0 `要修正`.

## Notes

- The templates are in `templates/`. Do not copy changes made in a workspace back into the templates (the templates are the same starting point for everyone).
- In a workspace that already has a skill with the same name (slides-build, etc.) in `.agents/skills/` or `.claude/skills/`, it is loaded twice along with the plugin's. doctor reports it as `要確認`, so ask the user which one to use.
