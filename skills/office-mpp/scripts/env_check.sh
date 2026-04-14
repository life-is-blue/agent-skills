#!/usr/bin/env bash
# office-mpp Environment Check
# Verifies all dependencies required by the office-mpp skill.
# Usage:
#   bash scripts/env_check.sh           # human-readable output
#   bash scripts/env_check.sh --json    # machine-readable JSON
# Exit codes: 0 = all OK, 2 = one or more required deps missing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

JSON_MODE=false
for arg in "$@"; do
    if [ "$arg" = "--json" ]; then
        JSON_MODE=true
    fi
done

STATUS=0
MISSING=()
FIX_COMMANDS=()

# ─── Helpers ───────────────────────────────────────────────────────────────

log() {
    if ! $JSON_MODE; then
        printf "%s\n" "$1"
    fi
}

check_ok() {
    if ! $JSON_MODE; then
        printf "[OK]      %-18s %s\n" "$1" "$2"
    fi
}

check_fail() {
    local name="$1" msg="$2" fix="$3"
    STATUS=2
    MISSING+=("$name")
    FIX_COMMANDS+=("$fix")
    if ! $JSON_MODE; then
        printf "[FAIL]    %-18s %s\n" "$name" "$msg"
        printf "E_ENV: Missing dependency: %s\n" "$name" >&2
        printf "           Fix: %s\n" "$fix"
    fi
}

check_warn() {
    if ! $JSON_MODE; then
        printf "[WARN]    %-18s %s\n" "$1" "$2"
        if [ -n "${3:-}" ]; then
            printf "           Fix: %s\n" "$3"
        fi
    fi
}

# ─── Detect OS ─────────────────────────────────────────────────────────────

OS="unknown"
case "$(uname -s)" in
    Darwin) OS="macos" ;;
    Linux)
        OS="linux"
        grep -qi microsoft /proc/version 2>/dev/null && OS="wsl"
        ;;
    MINGW*|MSYS*|CYGWIN*) OS="windows-shell" ;;
esac

# ─── Checks ────────────────────────────────────────────────────────────────

if ! $JSON_MODE; then
    log "=== office-mpp Environment Check ==="
    log ""
fi

# 1. python3 — REQUIRED (all scripts)
if command -v python3 &>/dev/null; then
    py_ver=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    check_ok "python3" "$py_ver"
else
    case "$OS" in
        macos)        fix="brew install python3" ;;
        linux|wsl)    fix="sudo dnf install python3  # or: sudo apt-get install python3" ;;
        windows-shell) fix="winget install Python.Python.3" ;;
        *)            fix="https://www.python.org/downloads/" ;;
    esac
    check_fail "python3" "not found — required for all scripts" "$fix"
fi

# 2. openpyxl — REQUIRED for EXPORT (mpp_to_excel.py)
if python3 -c "import openpyxl" 2>/dev/null; then
    opxl_ver=$(python3 -c "import openpyxl; print(openpyxl.__version__)" 2>/dev/null || echo "?")
    check_ok "openpyxl" "$opxl_ver (EXPORT required)"
else
    check_fail "openpyxl" "not found — required for Excel export (mpp_to_excel.py)" \
        "pip3 install openpyxl"
fi

# 3. java >= 17 — OPTIONAL (only needed for .mpp binary files via MPXJ)
if command -v java &>/dev/null; then
    java_ver_str=$(java -version 2>&1 | head -1)
    java_major=$(java -version 2>&1 | grep -oE '"[0-9]+' | head -1 | tr -d '"')
    if [ -n "$java_major" ] && [ "$java_major" -ge 17 ] 2>/dev/null; then
        check_ok "java" "$java_ver_str (>= 17, .mpp read enabled)"
    else
        check_warn "java" "$java_ver_str (< 17 — .mpp files need java >= 17)" \
            "sudo dnf install java-17-openjdk  # or: brew install openjdk@17"
    fi
else
    check_warn "java" "not found — .mpp binary files need java >= 17; .xml MSPDI works without java" \
        "sudo dnf install java-17-openjdk  # or: brew install openjdk@17"
fi

# 4. mpxj — OPTIONAL (only needed for .mpp binary files)
if python3 -c "import mpxj" 2>/dev/null; then
    mpxj_ver=$(python3 -c "import mpxj; print(getattr(mpxj, '__version__', '?'))" 2>/dev/null || echo "?")
    check_ok "mpxj" "$mpxj_ver (.mpp read enabled)"
else
    check_warn "mpxj" "not found — .mpp binary files need mpxj; .xml MSPDI works without it" \
        "pip3 install mpxj"
fi

# ─── Result ────────────────────────────────────────────────────────────────

if $JSON_MODE; then
    # Build JSON output
    missing_json="["
    first=true
    for m in "${MISSING[@]+"${MISSING[@]}"}"; do
        $first || missing_json+=","
        missing_json+="\"$m\""
        first=false
    done
    missing_json+="]"

    fix_json="["
    first=true
    for f in "${FIX_COMMANDS[@]+"${FIX_COMMANDS[@]}"}"; do
        $first || fix_json+=","
        fix_json+="\"$(echo "$f" | sed 's/"/\\"/g')\""
        first=false
    done
    fix_json+="]"

    if [ "$STATUS" -eq 0 ]; then
        ok_val="true"
    else
        ok_val="false"
    fi

    printf '{"ok": %s, "missing": %s, "fix_commands": %s}\n' \
        "$ok_val" "$missing_json" "$fix_json"
else
    log ""
    if [ "$STATUS" -eq 0 ]; then
        log "Status: READY"
    else
        log "Status: NOT READY — required dependency missing"
        log ""
        log "Apply fix commands above, then re-run: bash scripts/env_check.sh"
        exit 2
    fi
fi

exit "$STATUS"
