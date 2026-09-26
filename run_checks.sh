#!/usr/bin/env bash
# run_checks.sh — runs every check (PRD §6.2). Prints one PASS/FAIL line per check,
# then "X of Y checks passing". Exits non-zero if anything fails.
# Needs the developer set-up once: python3.12 scripts/setup.py --dev

set -u
cd "$(dirname "$0")"
ROOT="$(pwd)"
LOG_DIR="$(mktemp -d)"
trap 'rm -rf "$LOG_DIR"' EXIT

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
else
  echo "FAIL set-up: the Python environment is missing. Run: python3.12 scripts/setup.py --dev"
  exit 1
fi

TOTAL=0
PASSED=0
FAILED_NAMES=()

# check "<plain-language name>" <command...>
check() {
  local name="$1"
  shift
  TOTAL=$((TOTAL + 1))
  local log="$LOG_DIR/check_$TOTAL.log"
  if "$@" >"$log" 2>&1; then
    PASSED=$((PASSED + 1))
    echo "PASS $name"
  else
    FAILED_NAMES+=("$name")
    echo "FAIL $name"
    sed 's/^/     | /' "$log" | tail -n 40
  fi
}

echo "Process Map Studio checks"
echo "-------------------------"

# 10. Repository hygiene
check "Secret check (no API key, .env or data folder in git)" "$PY" scripts/check_secrets.py --all
check "README check (required sections, no placeholders, links work)" "$PY" scripts/check_readme.py

# 1. Static checks, backend (0 warnings)
check "Backend lint (ruff check)" "$PY" -m ruff check --no-cache backend scripts
check "Backend formatting (ruff format --check)" "$PY" -m ruff format --check --no-cache backend scripts
check "Backend type check (mypy app)" bash -c "cd backend && '$PY' -m mypy --no-incremental"
check "Launch scripts type check (mypy scripts)" \
  bash -c "cd backend && '$PY' -m mypy --strict --no-incremental ../scripts"

# 2-3. Architecture, unit and action tests
check "Backend tests (architecture, unit, actions; coverage >= 85% on services and actions)" \
  bash -c "cd backend && '$PY' -m pytest -p no:cacheprovider --cov --cov-report=term"

echo "-------------------------"
echo "$PASSED of $TOTAL checks passing"
if [ "$PASSED" -ne "$TOTAL" ]; then
  echo "Not passing:"
  for name in "${FAILED_NAMES[@]}"; do echo "  - $name"; done
  exit 1
fi
echo "ALL CHECKS PASSED"
