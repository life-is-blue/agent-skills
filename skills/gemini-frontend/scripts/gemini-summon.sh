#!/usr/bin/env bash
# gemini-summon.sh — call Gemini CLI in headless mode for front-end work.
#
# This wrapper standardises Gemini's prompt, flag set, and output parsing for
# multimodal front-end work.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  gemini-summon.sh <mode> "<brief>" [flags]
  gemini-summon.sh --status              # list recent stream sessions
  gemini-summon.sh --follow <path|latest>  # tail -f a stream session with human formatting

Modes
  design      Brief (+refs) -> new standalone HTML/CSS or component files
  implement   Brief + framework -> edits integrated into existing codebase
  polish      Existing files + feedback -> surgical edits in place

Flags
  --ref <path>          Multimodal reference (repeatable). Translated to @path.
  --target <path>       Working directory (cd before calling). Default: cwd.
  --framework <name>    auto|react|vue|svelte|html  (default: auto)
  --style <name>        auto|tailwind|css|styled    (default: auto)
  --read-only           Use plan approval mode; Gemini cannot write.
  --timeout <sec>       Default 300.
  --model <name>        Passthrough to gemini -m. Leave unset by default.
  --raw                 Emit raw Gemini JSON instead of human summary.
  --stream              Use -o stream-json; live tool/step timeline to stderr;
                        full NDJSON captured to /tmp/gemini-summon-*.ndjson.
                        Recommended for design/implement long runs.
EOF
}

# ---------- status / follow subcommands ----------
STREAM_DIR="/tmp"
STREAM_GLOB="$STREAM_DIR/gemini-summon-*.ndjson"

fmt_stream_line() {
  # jq filter: one NDJSON event in -> one human line out (or nothing).
  jq -r --unbuffered '
    if .type == "init" then
      "[gemini] session=\(.session_id[0:8]) model=\(.model)"
    elif .type == "tool_use" then
      "[gemini] → \(.tool_name)\(if .parameters.file_path then " (\(.parameters.file_path))" elif .parameters.dir_path then " (\(.parameters.dir_path))" else "" end)"
    elif .type == "tool_result" then
      "[gemini]   ← \(.status // "?")"
    elif .type == "result" then
      "[gemini] done: status=\(.status) tools=\(.stats.tool_calls // 0) tokens=\(.stats.total_tokens // 0) \(((.stats.duration_ms // 0) / 1000) | floor)s"
    elif .type == "error" then
      "[gemini] ERROR: \(.message // (. | tostring))"
    else empty end
  '
}

status_cmd() {
  shopt -s nullglob
  local files=("$STREAM_DIR"/gemini-summon-*.ndjson)
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No gemini-summon stream sessions in $STREAM_DIR."
    return 0
  fi
  echo "Recent gemini-summon sessions (newest first):"
  ls -1t "${files[@]}" | head -10 | while read -r f; do
    local age status tools tokens last_type
    age=$(( ($(date +%s) - $(stat -c %Y "$f")) ))
    last_type=$(tail -n 1 "$f" 2>/dev/null | jq -r '.type // "?"' 2>/dev/null || echo "?")
    if [[ "$last_type" == "result" ]]; then
      status=$(tail -n 1 "$f" | jq -r '.status // "?"')
      tools=$(tail -n 1 "$f" | jq -r '.stats.tool_calls // 0')
      tokens=$(tail -n 1 "$f" | jq -r '.stats.total_tokens // 0')
      printf "  %s  %ds ago  status=%s tools=%s tokens=%s\n" "$(basename "$f")" "$age" "$status" "$tools" "$tokens"
    else
      printf "  %s  %ds ago  last=%s (incomplete or running)\n" "$(basename "$f")" "$age" "$last_type"
    fi
  done
  echo
  echo "Follow live: $0 --follow latest"
}

follow_cmd() {
  local target="${1:-latest}"
  local file
  if [[ "$target" == "latest" ]]; then
    shopt -s nullglob
    local files=("$STREAM_DIR"/gemini-summon-*.ndjson)
    shopt -u nullglob
    if [[ ${#files[@]} -eq 0 ]]; then
      echo "No stream sessions to follow." >&2; exit 1
    fi
    file=$(ls -1t "${files[@]}" | head -1)
  else
    file="$target"
  fi
  [[ -f "$file" ]] || { echo "[gemini-summon] no such file: $file" >&2; exit 2; }
  echo "[gemini-summon] following $file (Ctrl-C to stop)" >&2
  tail -n +1 -F "$file" 2>/dev/null | fmt_stream_line
}

case "${1:-}" in
  --status) status_cmd; exit 0;;
  --follow) shift; follow_cmd "${1:-latest}"; exit 0;;
esac

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
STREAM=0

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
    --stream)     STREAM=1; shift;;
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
OUTPUT_MODE="json"
[[ $STREAM -eq 1 ]] && OUTPUT_MODE="stream-json"
GEMINI_ARGS=(-p "$PROMPT" -o "$OUTPUT_MODE")
if [[ $USE_YOLO -eq 1 ]]; then
  GEMINI_ARGS+=(--yolo)
else
  GEMINI_ARGS+=(--approval-mode plan)
fi
[[ -n "$MODEL" ]] && GEMINI_ARGS+=(-m "$MODEL")

# Gemini 0.40+ refuses to run in untrusted directories (exit 55). The wrapper
# already opts into yolo by default, so it IS the trust authority here — set
# the env var rather than make every caller export it. Caller can override by
# setting GEMINI_CLI_TRUST_WORKSPACE=false explicitly.
export GEMINI_CLI_TRUST_WORKSPACE="${GEMINI_CLI_TRUST_WORKSPACE:-true}"

START=$(date +%s)

if [[ $STREAM -eq 1 ]]; then
  # Stream path: tee NDJSON to a session file so --status / --follow can see it;
  # fork fmt_stream_line to stderr so the caller sees a live timeline.
  SESSION_FILE="$STREAM_DIR/gemini-summon-$(date +%s)-$$.ndjson"
  echo "[gemini-summon] stream session: $SESSION_FILE" >&2
  set +e
  (cd "$TARGET" && timeout "$TIMEOUT" gemini "${GEMINI_ARGS[@]}" 2>>"${SESSION_FILE}.err") \
    | tee "$SESSION_FILE" \
    | fmt_stream_line >&2
  # PIPESTATUS[0] is the gemini exit; its output is already captured in SESSION_FILE.
  RC=${PIPESTATUS[0]}
  set -e
  # For downstream parsing we look at the SESSION_FILE rather than keeping OUTPUT.
  OUTPUT=$(cat "$SESSION_FILE" 2>/dev/null; cat "${SESSION_FILE}.err" 2>/dev/null)
else
  set +e
  OUTPUT=$(cd "$TARGET" && timeout "$TIMEOUT" gemini "${GEMINI_ARGS[@]}" 2>&1)
  RC=$?
  set -e
  SESSION_FILE=""
fi

END=$(date +%s)
DURATION=$((END - START))

if [[ $RC -eq 124 ]]; then
  echo "[gemini-summon] timed out after ${TIMEOUT}s" >&2
  [[ -n "$SESSION_FILE" ]] && echo "[gemini-summon] partial stream: $SESSION_FILE" >&2
  exit 124
fi

if [[ $RC -eq 55 ]]; then
  echo "[gemini-summon] gemini refused untrusted workspace (exit 55)." >&2
  echo "[gemini-summon] Wrapper already exports GEMINI_CLI_TRUST_WORKSPACE=true; if this still fires, your gemini version may have changed the trust mechanism — try: gemini --skip-trust" >&2
  echo "$OUTPUT" >&2
  exit 55
fi

if [[ $RC -eq 42 ]]; then
  echo "[gemini-summon] gemini rejected input (exit 42 — invalid prompt/args). Check your brief and refs." >&2
  echo "$OUTPUT" >&2
  exit 42
fi

if [[ $RC -eq 53 ]]; then
  echo "[gemini-summon] gemini hit turn limit (exit 53). Break the task into smaller briefs." >&2
  echo "$OUTPUT" >&2
  exit 53
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

# Parse final response. Two shapes depending on output mode:
#   json         → single object with .response / .text / .output
#   stream-json  → NDJSON, concatenate assistant message.content (delta chunks)
RESPONSE=""
ERR=""
FILE_EDITS=0
TOOL_CALLS=0
if command -v jq >/dev/null 2>&1; then
  if [[ $STREAM -eq 1 && -n "$SESSION_FILE" && -f "$SESSION_FILE" ]]; then
    RESPONSE=$(jq -rs '
      [.[] | select(.type=="message" and .role=="assistant") | .content] | join("")
    ' "$SESSION_FILE" 2>/dev/null || true)
    TOOL_CALLS=$(jq -rs '[.[] | select(.type=="result") | .stats.tool_calls] | first // 0' "$SESSION_FILE" 2>/dev/null || echo 0)
    FILE_EDITS=$(jq -rs '[.[] | select(.type=="tool_use" and (.tool_name | test("write_file|replace|edit"; "i")))] | length' "$SESSION_FILE" 2>/dev/null || echo 0)
    ERR=$(jq -rs '[.[] | select(.type=="error") | .message // ""] | join("; ")' "$SESSION_FILE" 2>/dev/null || true)
  else
    RESPONSE=$(printf '%s' "$OUTPUT" | jq -r '.response // .text // .output // empty' 2>/dev/null || true)
    ERR=$(printf '%s' "$OUTPUT" | jq -r '.error // empty' 2>/dev/null || true)
  fi
fi

if [[ -n "$ERR" && "$ERR" != "null" ]]; then
  echo "[gemini-summon] gemini reported error: $ERR" >&2
  exit 1
fi

if [[ -z "$RESPONSE" ]]; then
  RESPONSE="$OUTPUT"
fi

YOLO_LABEL=$([[ $USE_YOLO -eq 1 ]] && echo on || echo off)
HEADER="[gemini-summon] mode=${MODE} framework=${FRAMEWORK} style=${STYLE} target=${TARGET} ${DURATION}s yolo=${YOLO_LABEL}"
if [[ $STREAM -eq 1 ]]; then
  HEADER+=" tools=${TOOL_CALLS} edits=${FILE_EDITS}"
fi

cat <<EOF
${HEADER}
---
${RESPONSE}
---
$([[ $STREAM -eq 1 ]] && echo "Stream log: $SESSION_FILE" || true)
Next: \`git diff --stat\` to inspect changes.
EOF
