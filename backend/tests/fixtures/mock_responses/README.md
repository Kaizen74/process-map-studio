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
