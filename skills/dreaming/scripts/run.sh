#!/bin/sh
# usage: cd <ワークスペース> && run.sh claude|codex|pi
# launchd や cron から、定期の整理を CLI で回す（launchd は WorkingDirectory にワークスペースを書く）。T3 Code・Claude Code Desktop・Codex app ではアプリに登録する（../schedule.md）。
set -eu
case ${1:-} in claude|codex|pi) ;; *) sed -n '2,3p' "$0" >&2; exit 2 ;; esac
ROOT=$(pwd -P)  # /tmp のようなリンクでも、Claude Code がメモリに使う実際のパスにする
[ -f "$ROOT/factory.toml" ] || { echo "factory.toml のあるフォルダ（ワークスペース）で回す: $ROOT" >&2; exit 2; }
MEM=$HOME/.claude/projects/$(printf %s "$ROOT" | tr '/._' '---')/memory
PROMPT=$(cat "$(dirname "$0")/../prompt.txt")
PATH=$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/local/bin:$PATH  # launchd の PATH は短い
echo "== $(date '+%F %T') dreaming $1"
case $1 in
claude) claude -p "$PROMPT" --permission-mode auto --add-dir "$MEM" ;;
codex) codex exec -C "$ROOT" -s workspace-write --skip-git-repo-check --add-dir "$MEM" "$PROMPT" ;;
pi) pi -p "$PROMPT" ;;
esac
