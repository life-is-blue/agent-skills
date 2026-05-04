#!/usr/bin/env bash
# gemini-summon.sh — call Gemini CLI in headless mode for front-end work.
#
# Why this exists: Gemini's multimodal vision and UI code generation are
# stronger than Claude's for front-end. This wrapper standardises the call
# so the main agent doesn't reinvent the prompt, flag set, or output parsing.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: gemini-summon.sh <mode> "<brief>" [flags]

Modes
  design      Brief (+refs) -> new standalone HTML/CSS or component files
  implement   Brief + framework -> edits integrated into existing codebase
  polish      Existing files + feedback -> surgical edits in place

Flags
  --ref <path>          Multimodal reference (repeatable). Translated to @path.
  --target <path>       Working directory (cd before calling). Default: cwd.
  --framework <name>    auto|react|vue|svelte|html  (default: auto)
  --style <name>        auto|tailwind|css|styled    (default: auto)
  --read-only           Drop --yolo; Gemini proposes but does not write.
  --timeout <sec>       Default 300.
  --model <name>        Passthrough to gemini -m. Leave unset by default.
  --raw                 Emit raw Gemini JSON instead of human summary.
EOF
}

# ---------- precheck ----------
if ! command -v gemini >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[gemini-summon] gemini CLI not found.

Install:
  npm install -g @google/gemini-cli

Then run `gemini` once interactively to authenticate.
EOF
  exit 127
fi

# ---------- arg parse ----------
MODE="${1:-}"
shift || true
BRIEF="${1:-}"
shift || true

if [[ -z "$MODE" || -z "$BRIEF" ]]; then
  usage >&2
  exit 2
fi

case "$MODE" in
  design|implement|polish) ;;
  *) echo "[gemini-summon] unknown mode: $MODE (need design|implement|polish)" >&2; exit 2;;
esac

REFS=()
TARGET="."
FRAMEWORK="auto"
STYLE="auto"
USE_YOLO=1
TIMEOUT=300
MODEL=""
RAW=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)        REFS+=("$2"); shift 2;;
    --target)     TARGET="$2"; shift 2;;
    --framework)  FRAMEWORK="$2"; shift 2;;
    --style)      STYLE="$2"; shift 2;;
    --read-only)  USE_YOLO=0; shift;;
    --timeout)    TIMEOUT="$2"; shift 2;;
    --model)      MODEL="$2"; shift 2;;
    --raw)        RAW=1; shift;;
    -h|--help)    usage; exit 0;;
    *) echo "[gemini-summon] unknown flag: $1" >&2; usage >&2; exit 2;;
  esac
done

if [[ ! -d "$TARGET" ]]; then
  echo "[gemini-summon] target dir not found: $TARGET" >&2
  exit 2
fi

# Resolve refs to absolute paths (helper may cd before invoking gemini).
REF_TOKENS=""
if [[ ${#REFS[@]} -gt 0 ]]; then
  for r in "${REFS[@]}"; do
    if [[ ! -e "$r" ]]; then
      echo "[gemini-summon] ref not found: $r" >&2
      exit 2
    fi
    abs=$(cd "$(dirname "$r")" && pwd)/$(basename "$r")
    REF_TOKENS="$REF_TOKENS @$abs"
  done
fi

# ---------- auto-detect framework / style ----------
PKG="$TARGET/package.json"

if [[ "$FRAMEWORK" == "auto" ]]; then
  if [[ -f "$PKG" ]]; then
    if   grep -q '"react"'   "$PKG" 2>/dev/null; then FRAMEWORK="react"
    elif grep -q '"vue"'     "$PKG" 2>/dev/null; then FRAMEWORK="vue"
    elif grep -q '"svelte"'  "$PKG" 2>/dev/null; then FRAMEWORK="svelte"
    else FRAMEWORK="html"
    fi
  else
    FRAMEWORK="html"
  fi
fi

if [[ "$STYLE" == "auto" ]]; then
  if [[ -f "$TARGET/tailwind.config.js" || -f "$TARGET/tailwind.config.ts" ]]; then
    STYLE="tailwind"
  elif [[ -f "$PKG" ]] && grep -q '"tailwindcss"' "$PKG" 2>/dev/null; then
    STYLE="tailwind"
  else
    STYLE="css"
  fi
fi

# ---------- build prompt ----------
case "$MODE" in
  design)
    SYS="You are a senior front-end designer. Produce production-ready ${FRAMEWORK} code with ${STYLE} styling. Output the smallest set of files needed and write them to disk under the current working directory. Use sensible defaults; do not pause to ask questions. Do not narrate between files."
    ;;
  implement)
    SYS="You are integrating a design into an existing ${FRAMEWORK} codebase. Match the project's existing conventions, reuse existing components where possible, and apply ${STYLE} styling. Edit files in place. Do not pause to ask questions; pick reasonable defaults."
    ;;
  polish)
    SYS="You are doing visual polish on existing ${FRAMEWORK} code. Make minimal, surgical edits — preserve structure, names, and exports. Address only the user's specific feedback. Do not refactor."
    ;;
esac

PROMPT="${SYS}

Task: ${BRIEF}${REF_TOKENS}"

# ---------- invoke ----------
GEMINI_ARGS=(-p "$PROMPT" -o json)
[[ $USE_YOLO -eq 1 ]] && GEMINI_ARGS+=(--yolo)
[[ -n "$MODEL" ]] && GEMINI_ARGS+=(-m "$MODEL")

# Gemini 0.40+ refuses to run in untrusted directories (exit 55). The wrapper
# already opts into yolo by default, so it IS the trust authority here — set
# the env var rather than make every caller export it. Caller can override by
# setting GEMINI_CLI_TRUST_WORKSPACE=false explicitly.
export GEMINI_CLI_TRUST_WORKSPACE="${GEMINI_CLI_TRUST_WORKSPACE:-true}"

START=$(date +%s)
set +e
OUTPUT=$(cd "$TARGET" && timeout "$TIMEOUT" gemini "${GEMINI_ARGS[@]}" 2>&1)
RC=$?
set -e
END=$(date +%s)
DURATION=$((END - START))

if [[ $RC -eq 124 ]]; then
  echo "[gemini-summon] timed out after ${TIMEOUT}s" >&2
  exit 124
fi

if [[ $RC -eq 55 ]]; then
  echo "[gemini-summon] gemini refused untrusted workspace (exit 55)." >&2
  echo "[gemini-summon] Wrapper already exports GEMINI_CLI_TRUST_WORKSPACE=true; if this still fires, your gemini version may have changed the trust mechanism — try: gemini --skip-trust" >&2
  echo "$OUTPUT" >&2
  exit 55
fi

if [[ $RC -ne 0 ]]; then
  echo "[gemini-summon] gemini exited with code $RC" >&2
  echo "$OUTPUT" >&2
  exit "$RC"
fi

# ---------- output ----------
if [[ $RAW -eq 1 ]]; then
  echo "$OUTPUT"
  exit 0
fi

# Parse JSON defensively. Gemini's headless JSON schema is not formally
# documented in the CLI help; we try common field names and fall back to raw.
RESPONSE=""
ERR=""
if command -v jq >/dev/null 2>&1; then
  # Try the documented headless fields first.
  RESPONSE=$(printf '%s' "$OUTPUT" | jq -r '.response // .text // .output // empty' 2>/dev/null || true)
  ERR=$(printf '%s' "$OUTPUT" | jq -r '.error // empty' 2>/dev/null || true)
fi

if [[ -n "$ERR" && "$ERR" != "null" ]]; then
  echo "[gemini-summon] gemini reported error: $ERR" >&2
  exit 1
fi

if [[ -z "$RESPONSE" ]]; then
  RESPONSE="$OUTPUT"
fi

cat <<EOF
[gemini-summon] mode=${MODE} framework=${FRAMEWORK} style=${STYLE} target=${TARGET} ${DURATION}s yolo=$([[ $USE_YOLO -eq 1 ]] && echo on || echo off)
---
${RESPONSE}
---
Next: \`git diff --stat\` to inspect changes.
EOF
