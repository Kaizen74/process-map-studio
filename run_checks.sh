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

# 1-3. Frontend: static checks (0 warnings), unit and component tests, production build
if [ -d frontend/node_modules ]; then
  check "Frontend lint (eslint, incl. the components import rule)" \
    npm --prefix frontend run --silent lint
  check "Frontend type check (tsc --noEmit)" npm --prefix frontend run --silent typecheck
  check "Design tokens in sync (tokens.css matches shared/design_tokens.json)" \
    npm --prefix frontend run --silent tokens:check
  check "Frontend tests (vitest)" npm --prefix frontend run --silent test
  check "Frontend build (the page the app serves)" npm --prefix frontend run --silent build
  # Use a preinstalled Chromium when the computer provides one (cloud build machines).
  if [ -z "${PMS_CHROMIUM_PATH:-}" ] && [ -x /opt/pw-browsers/chromium ]; then
    export PMS_CHROMIUM_PATH=/opt/pw-browsers/chromium
  fi
  check "Browser checks (accessibility on every screen, fonts offline, smoke path, visual baseline)" \
    npm --prefix frontend run --silent e2e
else
  TOTAL=$((TOTAL + 1))
  FAILED_NAMES+=("Frontend checks")
  echo "FAIL Frontend checks: packages not installed. Run: python3.12 scripts/setup.py --dev"
fi

# 2-3. Architecture, unit and action tests
# The speed tests (p95 < 200 ms) run without the coverage tracer, which roughly doubles the time
# of Python-heavy endpoints and so measured the tracer rather than the app (2026-10-06).
check "Backend tests (architecture, unit, actions; coverage >= 85% on services and actions)" \
  bash -c "cd backend && '$PY' -m pytest -p no:cacheprovider -n auto --cov --cov-report=term --ignore=tests/latency --ignore=tests/reality_checks && '$PY' -m pytest -p no:cacheprovider tests/latency"

# 4. Reality checks RQ1-RQ10 (PRD §5.12.8, from P13d): the snapshot, Leadership and the Reality
# pack on fixture A.12, and the token scan of the Reality components (RQ3). The printed pages'
# label overlaps and text sizes (RQ7) are measured in a real browser by the browser checks.
if [ -d frontend/node_modules ]; then
  check "Reality checks (RQ1-RQ10)" \
    bash -c "cd backend && '$PY' -m pytest -p no:cacheprovider tests/reality_checks && cd ../frontend && npx vitest run tests/unit/designSystem.test.ts -t RQ3"
else
  check "Reality checks (RQ1-RQ10)" bash -c "cd backend && '$PY' -m pytest -p no:cacheprovider tests/reality_checks"
fi

echo "-------------------------"
echo "$PASSED of $TOTAL checks passing"
if [ "$PASSED" -ne "$TOTAL" ]; then
  echo "Not passing:"
  for name in "${FAILED_NAMES[@]}"; do echo "  - $name"; done
  exit 1
fi
echo "ALL CHECKS PASSED"
