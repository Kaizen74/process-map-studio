# Mock AI responses (illustrative only)

Canned answers returned by `app/services/ai_service.py` when `MOCK_CLAUDE=1`, so tests and
rehearsals run offline with no API key (PRD constraint 13). Layout: `<stage_id>/<key>.json`,
falling back to `<stage_id>/default.json`. They are not real Anthropic data.

- `models_get/` — answer for `GET /v1/models/{id}` (shape of the SDK's `ModelInfo`)
- `models_list/` — answer for `GET /v1/models`
