# pi のパッケージとして入れる

AI Deck Factory を pi（`@earendil-works/pi-coding-agent`）のパッケージとして、1 つのワークスペース（プロジェクト）だけに入れる手順。ほかのフォルダの pi には出ない。2026-10-12 に pi 1.0.0 で確かめた。Claude Code で使う手順は [claude-code-plugin.md](claude-code-plugin.md)、開発しながら試す手順は [development.md](development.md)。

## 入れる

ワークスペースにするフォルダで、`-l`（`--local`）を付けて入れる。付けないと `~/.pi/agent/settings.json` に入り、どのフォルダの pi にも出る。

```sh
cd <ワークスペース>
pi install -l ~/Projects/ai-deck-factory                           # 手元の checkout をそのまま読む（写さない）
pi install -l git:github.com/mats16/ai-deck-factory   # git から
```

- 書き込まれるのは `<ワークスペース>/.pi/settings.json` の `packages`。手元のパスは `.pi/` からの相対のパスで入るので、ワークスペースか checkout を動かしたら入れ直す。
- 入るもの（`package.json` の `pi`）: `skills/` の 10 個のスキルと、`extensions/rules.ts`（プラグインのファイルを read・bash で開いたら、ワークスペースの `rules/` の同じパスを、顧客の資料の `構成案*.md` などを開いたら顧客の `memory.md` を続けて出す）。
- スキルは `/skill:factory-init` のように呼ぶ。入れたら `factory-init`、続けて `factory-doctor`（README の「入れ方」）。

## project trust

`.pi/settings.json` のパッケージは、そのフォルダを信頼したときだけ読まれる（pi の `docs/security.md` の「project trust」）。

- 対話の pi は、初めて開いたときに聞く。`/trust` で決めたことは `~/.pi/agent/trust.json` に残り、親のフォルダの決定も子に効く（ホームを信頼していれば、その下はすべて読まれる）。
- `pi -p`・`--mode json`・`--mode rpc` は聞けない。決めていないフォルダでは読まれない。定期に回すもの（dreaming の `run.sh pi`）と `pi -p` の子のために、ワークスペースの trust は `/trust` で保存しておく。`--approve` を付けるとその回だけ読まれるが、保存した「信頼しない」も上書きするので、決まった仕組みには入れない。
- `--no-approve` で回すと、このパッケージのスキルは 1 つも出ない。

## そのフォルダだけで効いているかを確かめる

```sh
cd <ワークスペース> && pi list   # Project packages に出る
cd ~ && pi list                   # User packages にだけ出る（ここに ai-deck-factory が出たら、-l なしで入っている）
```

スキルの出どころは、対話の pi の起動の表示か、RPC の `get_commands` で見る（モデルは呼ばない）。

```sh
(echo '{"type":"get_commands"}'; sleep 6) | pi --mode rpc --no-session | grep -o '"name":"skill:[^"]*"'
```

ワークスペースでは 10 個（`factory-init` … `factory-kaizen`）が `scope: project` で出て、ほかのフォルダでは出ない。何も出ないときは、trust を保存していない（上の「project trust」）か、起動が返事より遅れている。`/trust` で保存するか、`sleep` を延ばしてもう一度回す。

## pi はワークスペースの直下で起こす

`.pi/settings.json` は、pi を起こしたフォルダのものだけが読まれ、親はたどらない。ワークスペースの下（`Internal/<資料>/` など）で起こすと、パッケージのスキルも拡張も 0 になる。`AGENTS.md` は親からも読まれるので、決まりは見えるのにスキルがない状態で動く。

- 対話の pi、`pi -p` の子（レビューを頼むとき）とも、ワークスペースの直下で起こす。資料のフォルダへは、起こしたあと `cd` で入る。
- `.agents/skills/` に置いたスキルは親からも見つかる（git のリポジトリの根元まで）ので、`~/Documents/Internal` で起こしても読まれていた。パッケージに移すと、ここが変わる。

## 同じ名前のスキルがあるとき

パッケージのスキルは、pi の中でいちばん優先が低い。同じ名前のスキルがほかにあると、そちらが勝ち、パッケージのものは読まれない（pi は名前がぶつかると優先の高いものを残して警告を出す）。勝つのは、ワークスペースか親の `.agents/skills/`（git のリポジトリならその根元まで）、`.pi/skills/`、ユーザーの `~/.agents/skills/`・`~/.pi/agent/skills/`、settings.json の `skills` に書いたもの。前から `.agents/skills/deck-build` などを置いていたフォルダに入れると、古いスキルのまま動く。移すときは `.agents/skills/` の同じ名前のものを外す（README の「残っている課題」の「Documents を移す」）。`factory-doctor` の「スキルの重なり」が見るのはワークスペースの直下の `.agents/skills/`・`.claude/skills/` だけなので、ほかの場所のものは、上の `get_commands` を grep なしで回し、スキルの `sourceInfo.path` と `scope` で出どころを見る。

## 外す

```sh
cd <ワークスペース>
pi remove -l ~/Projects/ai-deck-factory   # 入れたときと同じ書き方で
```

ワークスペースのファイル（`factory.toml`・`AGENTS.md`・`rules/`・`.factory/`）は残る。
