#!/bin/bash
# Process Map Studio: one-time setup for macOS (run again after every update). See README.md step 3.
cd "$(dirname "$0")" || exit 1
PY=""
for candidate in python3.12 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.12 was not found."
  echo "Install it: go to python.org -> Downloads -> download Python 3.12 for macOS -> open the installer."
  echo "Then double-click Setup.command again (README step 1)."
  read -r -p "Press Enter to close this window." _
  exit 1
fi
"$PY" scripts/setup.py "$@"
STATUS=$?
echo
read -r -p "Press Enter to close this window." _
exit $STATUS
