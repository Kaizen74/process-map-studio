# Mock AI responses (illustrative only)

Canned answers returned by `app/services/ai_service.py` when `MOCK_CLAUDE=1`, so tests and
rehearsals run offline with no API key (PRD constraint 13). Layout: `<stage_id>/<key>.json`,
falling back to `<stage_id>/default.json`. They are not real Anthropic data.

- `models_get/` — answer for `GET /v1/models/{id}` (shape of the SDK's `ModelInfo`)
- `models_list/` — answer for `GET /v1/models`
- Pipeline stages (from phase P3), e.g. `S1_extract_interview/<input_hash>.json`: the JSON answer
  a stage call returns, checked against that stage's schema. The key is
  `ai_service.input_hash(stage_id, blocks)` (the stage plus the source data sent, not the prompt
  wording). `R_repair/<input_hash>.json` answers the one repair call for the call with that hash.
- Gap analysis A (phase P10): `GA_internal/<input_hash>.json` answers the documents-vs-practice call for the drafted sample (the A.7 findings and the unexplained cause, keyed by the divergence set as sent) and `GA_verify/<input_hash>.json` its verifier call; both have an empty `default.json`. Built by `python tests/fixtures/make_ai_fixtures.py gap` (also run by the full generator).
- Web research (phase P10), e.g. `GB_research/<key>.json` and `GB_test/default.json`: `{"responses": [<Messages API response>, …]}` — one response per request of the turn (a paused turn has several), validated with the SDK's own `Message` type, with `server_tool_use`, `web_search_tool_result` and cited text blocks as the API returns them; or `{"error": "web_search_disabled"}` for an organisation with web search switched off. The key is `ai_service.research_key(call)`: the stage, the brief and the search-tool settings (what is actually sent). URLs in these fixtures are illustrative (`example.org` and similar), never real findings.
