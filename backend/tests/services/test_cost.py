"""Draft cost estimate (deep review item 5): assumed until a real draft has run, then measured;
priced from the dated list, or no price when the model isn't on it."""

from __future__ import annotations

from app.domain.result import Err, Ok
from app.services import cost

PRICES = cost.Prices(checked_on="2026-10-19", per_million={"claude-opus-5-5": (4.0, 20.0)})


def test_assumed_until_a_real_draft_has_run() -> None:
    found = cost.estimate(100_000, [], "claude-opus-5-5", PRICES)
    assert (found.input_tokens, found.output_tokens, found.basis, found.drafts_measured) == (
        100_000, 50_000, "assumed", 0)  # fmt: skip
    assert found.cost_usd == round((100_000 * 4 + 50_000 * 20) / 1_000_000, 2) == 1.4


def test_measured_from_real_drafts_weighted_by_their_size() -> None:
    history = [cost.Usage(10_000, 30_000, 5_000), cost.Usage(30_000, 50_000, 15_000),
               cost.Usage(0, 9_999, 9_999),  # read nothing: left out
               cost.Usage(5_000, 0, 0)]  # no real call: left out  # fmt: skip
    found = cost.estimate(20_000, history, "claude-opus-5-5", PRICES)
    assert found.basis == "measured" and found.drafts_measured == 2
    assert (found.input_tokens, found.output_tokens) == (40_000, 10_000)  # 2.0 and 0.5 a char


def test_no_price_means_no_amount_never_a_guess() -> None:
    found = cost.estimate(1_000, [], "claude-some-new-model", PRICES)
    assert found.cost_usd is None and found.input_tokens == 1_000


def test_the_price_list_is_read_or_refused_plainly() -> None:
    listed = '{"checked_on": "2026-10-19", "models": {"m": {"input": 1, "output": 2}}}'
    match cost.read_prices(listed):
        case Ok(value=prices):
            assert prices.per_million == {"m": (1.0, 2.0)} and prices.checked_on == "2026-10-19"
        case Err():
            raise AssertionError
    for broken in ("", "[]", '{"checked_on": "x"}', '{"checked_on": "x", "models": {"m": {}}}'):
        assert isinstance(cost.read_prices(broken), Err)


def test_the_shipped_price_list_reads_and_prices_the_default_model() -> None:
    from app.config import MODEL_PRICES_FILE, SETTING_DEFAULTS

    match cost.read_prices(MODEL_PRICES_FILE.read_text(encoding="utf-8")):
        case Ok(value=prices):
            assert SETTING_DEFAULTS["ANTHROPIC_MODEL"] in prices.per_million
        case Err():
            raise AssertionError("shared/model_prices.json doesn't read")
