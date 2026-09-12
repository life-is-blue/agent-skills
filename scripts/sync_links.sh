#!/usr/bin/env bash
#
# sync_links.sh - Link this repository's scoped skills into every client skill
# directory, and diagnose drift.
#
# The link scope is declared in SCOPED below. skills/catalog.json is the
# authoritative inventory of every skill in the repository, so `status` can also
# report skills that exist but are deliberately not linked.
#
# Usage:
#   ./sync_links.sh                    # status: diagnose all clients (read-only)
#   ./sync_links.sh status             # same as above
#   ./sync_links.sh check              # status, but exit 1 on any drift
#   ./sync_links.sh sync [--dry-run]   # link every scoped skill; prune stale links
#   ./sync_links.sh link <name>... [--dry-run]
#   ./sync_links.sh unlink <name>... [--dry-run]
#
# Safety: a real file or directory sitting at a target path is reported and
# skipped, never overwritten. `ln -sfn` would otherwise nest the link *inside*
# that directory and still exit 0, which is how shadowing directories silently
# accumulate. Links are always created with plain `ln -s` after an explicit
# absence check.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SIBLINGS="$(cd "${REPO_ROOT}/.." && pwd)"
CATALOG="${REPO_ROOT}/skills/catalog.json"

TARGETS=(
  "${HOME}/.agents/skills"
  "${HOME}/.codex/skills"
  "${HOME}/.codebuddy/skills"
  "${HOME}/.claude/skills"
  "${HOME}/.tclaude/skills"
)

# Scoped links, as "name=source". In-repo skills live under skills/; the rest are
# sibling checkouts. Only these names are ever linked into a client.
SCOPED=(
  "coding-agent=${REPO_ROOT}/skills/coding-agent"
  "coordinator=${REPO_ROOT}/skills/coordinator"
  "search-docs=${REPO_ROOT}/skills/search-docs"
  "cnb-api=${SIBLINGS}/cnb-skill/skills/cnb-api"
  "cnb-pipeline=${SIBLINGS}/cnb-skill/skills/cnb-pipeline"
  "wecom-unified=${SIBLINGS}/wecom-unified/skills/wecom-unified"
)

# Source trees this script owns links into. A symlink pointing anywhere else
# (a hub install, another tool, a hand-made link) is never pruned or rewritten.
SOURCE_ROOTS=(
  "${REPO_ROOT}/skills"
  "${SIBLINGS}/cnb-skill/skills"
  "${SIBLINGS}/wecom-unified/skills"
)

DRY=0
CMD=""
NAMES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    -h|--help) CMD="help" ;;
    *)
      if [ -z "$CMD" ]; then CMD="$1"; else NAMES="${NAMES} $1"; fi
      ;;
  esac
  shift
done
[ -n "$CMD" ] || CMD="status"

DRY_LABEL=""
if [ "$DRY" = 1 ]; then DRY_LABEL=" (dry-run)"; fi

# Skill names are hyphen-case, so unquoted word splitting over NAMES is safe.
scope_source() {
  local entry
  for entry in "${SCOPED[@]}"; do
    if [ "${entry%%=*}" = "$1" ]; then
      printf '%s\n' "${entry#*=}"
      return 0
    fi
  done
  return 1
}

# True when $1 is a symlink this script owns and may prune.
is_owned_link() {
  local dest="$1" src root
  [ -L "$dest" ] || return 1
  src="$(readlink "$dest")"
  for root in "${SOURCE_ROOTS[@]}"; do
    case "$src" in
      "${root}/"*) return 0 ;;
    esac
  done
  return 1
}

# True when a symlink already resolves to $2. Compares resolved paths, so an
# unnormalised spelling such as "repo/../sibling/skills/x" is not mistaken for a
# different target and needlessly rewritten.
same_target() {
  local a b
  a="$(cd "$1" 2>/dev/null && pwd -P)" || return 1
  b="$(cd "$2" 2>/dev/null && pwd -P)" || return 1
  [ "$a" = "$b" ]
}

# link_one <target_dir> <name> <source>
# 0 = linked or already correct; 1 = refused because a real path is in the way.
link_one() {
  local target_dir="$1" name="$2" source="$3"
  local dest="${target_dir}/${name}"

  if [ -L "$dest" ]; then
    if same_target "$dest" "$source"; then
      return 0
    fi
    if [ "$DRY" = 1 ]; then
      echo "  ~ relink ${name} (was -> $(readlink "$dest"))"
      return 0
    fi
    rm -f "$dest"
    ln -s "$source" "$dest"
    echo "  ~ relinked ${name}"
    return 0
  fi

  if [ -e "$dest" ]; then
    echo "  !! REFUSED ${dest}" >&2
    echo "     A real file or directory is in the way, not a symlink." >&2
    echo "     \`ln\` would nest a link inside it, so nothing was written." >&2
    echo "     Move it aside (or delete it) and re-run." >&2
    return 1
  fi

  if [ "$DRY" = 1 ]; then
    echo "  + link ${name}"
    return 0
  fi
  mkdir -p "$target_dir"
  ln -s "$source" "$dest"
  echo "  + linked ${name}"
  return 0
}

# unlink_one <target_dir> <name>
unlink_one() {
  local target_dir="$1" name="$2"
  local dest="${target_dir}/${name}"

  if [ -L "$dest" ]; then
    if [ "$DRY" = 1 ]; then
      echo "  - unlink ${name}"
      return 0
    fi
    rm -f "$dest"
    echo "  - unlinked ${name}"
    return 0
  fi

  if [ -e "$dest" ]; then
    echo "  !! skipped ${dest}: real path, not a symlink" >&2
    echo "     It permanently shadows this skill until moved aside." >&2
    return 1
  fi
  return 0
}

catalog_names() {
  [ -f "$CATALOG" ] || return 0
  python3 - "$CATALOG" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as exc:
    sys.stderr.write(f"warning: cannot read catalog: {exc}\n")
    raise SystemExit(0)
for entry in data.get("skills", []):
    name = entry.get("name")
    if name:
        print(name)
PY
}

cmd_status() {
  local strict="$1" drift=0
  echo "=== Scoped links (${#SCOPED[@]}) ==="
  for entry in "${SCOPED[@]}"; do
    printf '  %-18s %s\n' "${entry%%=*}" "${entry#*=}"
  done

  echo ""
  echo "=== Unscoped repository skills (intentionally not linked) ==="
  local catalog
  catalog="$(catalog_names)"
  local unscoped="" name
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    scope_source "$name" >/dev/null || unscoped="${unscoped} ${name}"
  done <<< "$catalog"
  if [ -z "$unscoped" ]; then
    echo "  (none)"
  else
    for name in $unscoped; do echo "  -${name}"; done
  fi

  echo ""
  echo "=== Client state ==="
  local target dest base src
  for target in "${TARGETS[@]}"; do
    printf '%s\n' "$target"
    if [ ! -d "$target" ]; then
      echo "  (directory not present)"
      continue
    fi

    for entry in "${SCOPED[@]}"; do
      name="${entry%%=*}"
      dest="${target}/${name}"
      if [ -L "$dest" ]; then
        src="$(readlink "$dest")"
        if same_target "$dest" "${entry#*=}"; then
          echo "  ok       ${name}"
        else
          echo "  RELINK   ${name} -> ${src}"
          drift=$((drift + 1))
        fi
      elif [ -e "$dest" ]; then
        echo "  SHADOWED ${name} (real path in the way)"
        drift=$((drift + 1))
      else
        echo "  MISSING  ${name}"
        drift=$((drift + 1))
      fi
    done

    for dest in "$target"/*; do
      [ -e "$dest" ] || [ -L "$dest" ] || continue
      base="$(basename "$dest")"
      scope_source "$base" >/dev/null && continue
      if is_owned_link "$dest"; then
        echo "  STALE    ${base} -> $(readlink "$dest")"
        drift=$((drift + 1))
      elif [ -L "$dest" ]; then
        echo "  foreign  ${base} -> $(readlink "$dest")"
      elif [ "$base" != ".system" ]; then
        # .system is Codex's own directory; everything else real is worth seeing.
        echo "  foreign  ${base} (real directory)"
      fi
    done
  done

  echo ""
  if [ "$drift" -eq 0 ]; then
    echo "No drift."
    return 0
  fi
  echo "Drift: ${drift} item(s) need attention."
  if [ "$strict" = 1 ]; then return 1; fi
  return 0
}

cmd_sync() {
  local rc=0 target entry name src
  echo "=== sync${DRY_LABEL} ==="
  for target in "${TARGETS[@]}"; do
    echo "${target}"
    for entry in "${SCOPED[@]}"; do
      name="${entry%%=*}"
      src="${entry#*=}"
      if [ ! -d "$src" ]; then
        echo "  !! source missing for ${name}: ${src}" >&2
        rc=1
        continue
      fi
      link_one "$target" "$name" "$src" || rc=1
    done

    for entry in "$target"/*; do
      [ -e "$entry" ] || [ -L "$entry" ] || continue
      name="$(basename "$entry")"
      scope_source "$name" >/dev/null && continue
      is_owned_link "$entry" || continue
      if [ "$DRY" = 1 ]; then
        echo "  - prune ${name}"
      else
        rm -f "$entry"
        echo "  - pruned ${name}"
      fi
    done
  done
  return "$rc"
}

cmd_link() {
  local rc=0 target name src
  [ -n "$NAMES" ] || { echo "Error: link needs at least one skill name." >&2; return 1; }
  for name in $NAMES; do
    if ! src="$(scope_source "$name")"; then
      echo "Error: '${name}' is not in the link scope in $0." >&2
      echo "Add it to SCOPED first if it should reach every client." >&2
      return 1
    fi
    [ -d "$src" ] || { echo "Error: source missing for ${name}: ${src}" >&2; return 1; }
  done
  echo "=== link${DRY_LABEL} ==="
  for target in "${TARGETS[@]}"; do
    echo "${target}"
    for name in $NAMES; do
      src="$(scope_source "$name")"
      link_one "$target" "$name" "$src" || rc=1
    done
  done
  return "$rc"
}

cmd_unlink() {
  local rc=0 target name
  [ -n "$NAMES" ] || { echo "Error: unlink needs at least one skill name." >&2; return 1; }
  echo "=== unlink${DRY_LABEL} ==="
  for target in "${TARGETS[@]}"; do
    echo "${target}"
    for name in $NAMES; do
      unlink_one "$target" "$name" || rc=1
    done
  done
  return "$rc"
}

case "$CMD" in
  status) cmd_status 0 ;;
  check) cmd_status 1 ;;
  sync) cmd_sync ;;
  link) cmd_link ;;
  unlink) cmd_unlink ;;
  help|*)
    sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    [ "$CMD" = "help" ] || { echo "" >&2; echo "Unknown command: ${CMD}" >&2; exit 1; }
    ;;
esac
