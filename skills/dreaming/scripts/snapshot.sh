#!/bin/sh
# usage: cd <ワークスペース> && snapshot.sh save | diff <tar.gz> | restore <tar.gz>
# 定期の整理の前に、指示（AGENTS.md・CLAUDE.md・rules/）、索引、調べ直しの記録（Research/deck_research/）、スキル（factory.toml の [factory] source のリポジトリ）、Claude Code のメモリを固めて残す。
# diff はその写しから後の変更を出し、restore はその写しに戻す（写しのあとに足したファイルは消さない）。
# 写しはワークスペースの .factory/dreaming/backup/。lint の記録（.factory/lint_runs.jsonl）は、戻すと消えるので入れない。
set -eu
ROOT=$(pwd)
[ -f "$ROOT/factory.toml" ] || { echo "factory.toml のあるフォルダ（ワークスペース）で回す: $ROOT" >&2; exit 2; }
MEM=$HOME/.claude/projects/$(printf %s "$ROOT" | tr '/._' '---')/memory
SRC=$(sed -n 's/^source *= *"\([^"]*\)".*/\1/p' "$ROOT/factory.toml" | head -1 | sed "s|^~|$HOME|")
DIR=$ROOT/.factory/dreaming/backup
PATHS=""
for p in "$ROOT/AGENTS.md" "$ROOT/CLAUDE.md" "$ROOT/references_index.md" "$ROOT/rules" "$ROOT/Research/deck_research" "${SRC:+$SRC/skills}" "${SRC:+$SRC/agents}" "$MEM"; do
  [ -e "$p" ] && PATHS="$PATHS ${p#/}"
done
case ${1:-} in
save)
  mkdir -p "$DIR"
  out=$DIR/$(date +%Y%m%d_%H%M%S).tar.gz
  tar czf "$out" -C / --exclude '__pycache__' $PATHS
  ls -t "$DIR"/*.tar.gz | tail -n +9 | while read -r f; do rm -f "$f"; done  # 新しい 8 個だけ残す
  echo "$out" ;;
diff)
  t=$(mktemp -d)
  tar xzf "$2" -C "$t"
  for p in $PATHS; do diff -ruN -x __pycache__ "$t/$p" "/$p" || true; done
  rm -rf "$t" ;;
restore)
  tar xzf "$2" -C /
  echo "restored: $2" ;;
*) sed -n '2,5p' "$0" >&2; exit 2 ;;
esac
