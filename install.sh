#!/usr/bin/env bash
# 하네스 시작 묶음을 대상 프로젝트에 복사한다. 이미 있는 파일은 덮어쓰지 않는다.
# 사용법: bash install.sh <대상 프로젝트 폴더> [--hook]
#   --hook  완료 훅(Stop)을 바로 켠다. .claude/settings.json 이 없을 때만 만든다.
set -euo pipefail
TARGET="${1:-}"
HOOK="${2:-}"
if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "사용법: bash install.sh <대상 프로젝트 폴더> [--hook]" >&2
  exit 1
fi
SRC="$(cd "$(dirname "$0")" && pwd)/template"
copied=0; skipped=0
while IFS= read -r -d '' f; do
  rel="${f#"$SRC"/}"
  # 묶음 안에서는 dot-claude/ 로 보관하고, 설치할 때 .claude/ 로 바꾼다.
  case "$rel" in dot-claude/*) rel=".claude/${rel#dot-claude/}";; esac
  dest="$TARGET/$rel"
  if [ -e "$dest" ]; then
    echo "건너뜀(이미 있음): $rel"; skipped=$((skipped+1))
  else
    mkdir -p "$(dirname "$dest")"; cp "$f" "$dest"
    echo "복사: $rel"; copied=$((copied+1))
  fi
done < <(find "$SRC" -type f -print0)

IGNORE=".claude/hooks/.jev_done_state.json"
touch "$TARGET/.gitignore"
if ! grep -qxF "$IGNORE" "$TARGET/.gitignore"; then
  # 마지막 줄에 줄바꿈이 없으면 먼저 넣어서 두 줄이 붙지 않게 한다.
  if [ -s "$TARGET/.gitignore" ] && [ -n "$(tail -c 1 "$TARGET/.gitignore")" ]; then
    echo >> "$TARGET/.gitignore"
  fi
  echo "$IGNORE" >> "$TARGET/.gitignore"
fi

if [ "$HOOK" = "--hook" ]; then
  if [ -e "$TARGET/.claude/settings.json" ]; then
    echo "settings.json 이 이미 있다. settings.stop-hook.example.json 의 내용을 직접 병합해야 한다."
  else
    cp "$SRC/dot-claude/settings.stop-hook.example.json" "$TARGET/.claude/settings.json"
    echo "완료 훅을 켰다: .claude/settings.json"
  fi
fi
echo "끝: 복사 $copied개, 건너뜀 $skipped개"
echo "다음 할 일: GOAL.md 에 목표와 완료 조건을 적는다."
