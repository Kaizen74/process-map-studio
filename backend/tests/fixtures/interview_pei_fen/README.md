# Sample interview (real, not illustrative)

`Interview_with_Pei_Fen_otter_ai_transcript.txt` is a real recorded conversation, exported from
Otter.ai, supplied by Eric on 2026-09-29 and kept **exactly as exported** (byte for byte, CRLF line
endings; see `.gitattributes`). It is the one exception to "fixtures are illustrative only"
(Eric's decision, DECISIONS.md 2026-09-29).

- Used to test an interview-only engagement: reading Otter exports, readiness and the Limited
  signal strength (offline, `tests/unit/test_sample_interview.py`), and the live interview-only
  check (`tests/live/test_live_interview.py`, only when Eric runs it).
- It names real people. The tests put every name on the engagement's redaction list
  (`tests/sample_interview.py`), so no name reaches the map, the AI answers or an export, and a
  test checks that.
- It stays in Eric's private repository only. Keep it only while the participants' agreement
  covers this use; if it doesn't, delete this folder and the tests that use it.
