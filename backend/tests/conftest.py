"""Shared test settings. Every test runs offline with Claude mocked (PRD constraint 13)."""

from __future__ import annotations

import os

os.environ.setdefault("MOCK_CLAUDE", "1")
