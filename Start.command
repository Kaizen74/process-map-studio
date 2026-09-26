#!/bin/bash
# Process Map Studio: start the app on macOS. Close this window to stop it. See README.md.
cd "$(dirname "$0")" || exit 1
PY=""
for candidate in python3.12 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.12 was not found. Install it from python.org (README step 1), then run Setup.command."
  read -r -p "Press Enter to close this window." _
  exit 1
fi
"$PY" scripts/start.py "$@"
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo
  read -r -p "Press Enter to close this window." _
fi
exit $STATUS
