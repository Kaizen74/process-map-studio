"""Draft cost estimate (deep review item 5, 2026-10-19; API_CONTRACT.md → Draft → estimate).

Pure: how many tokens a draft of so many characters will probably use, and what that costs at
the model's price. Until a real draft has run on this computer the ratio is assumed (a rough
rule: each character is read about four times across the stages, at about four characters a
token, and the answers and the model's thinking add about half as much again); after that it is
measured from the real drafts' own usage. Mock calls never count.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.result import Err, ErrorKind, Ok, Result

ASSUMED_INPUT_PER_CHAR = 1.0
ASSUMED_OUTPUT_PER_CHAR = 0.5
MEASURED_DRAFTS = 5  # the most recent real drafts the ratio is measured from
BAD_PRICES = "The model price list (shared/model_prices.json) couldn't be read."


@dataclass(frozen=True, slots=True)
class Usage:
    """One real draft: the characters it read and the tokens it used."""

    characters: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class Prices:
    checked_on: str
    per_million: Mapping[str, tuple[float, float]]  # model → (input, output) US$ per MTok


@dataclass(frozen=True, slots=True)
class Estimate:
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    basis: str  # "assumed" or "measured"
    drafts_measured: int


def read_prices(text: str) -> Result[Prices]:
    try:
        data = json.loads(text)
        models = {str(model): (float(p["input"]), float(p["output"]))
                  for model, p in data["models"].items()}  # fmt: skip
        return Ok(Prices(checked_on=str(data["checked_on"]), per_million=models))
    except (ValueError, KeyError, TypeError, AttributeError):
        return Err(ErrorKind.IO, BAD_PRICES)


def estimate(characters: int, history: Sequence[Usage], model: str, prices: Prices) -> Estimate:
    usable = [u for u in history if u.characters > 0 and u.input_tokens > 0]
    if usable:
        chars = sum(u.characters for u in usable)
        per_in = sum(u.input_tokens for u in usable) / chars
        per_out = sum(u.output_tokens for u in usable) / chars
        basis = "measured"
    else:
        per_in, per_out, basis = ASSUMED_INPUT_PER_CHAR, ASSUMED_OUTPUT_PER_CHAR, "assumed"
    tokens_in, tokens_out = round(characters * per_in), round(characters * per_out)
    price = prices.per_million.get(model)
    cost = None
    if price is not None:
        cost = round((tokens_in * price[0] + tokens_out * price[1]) / 1_000_000, 2)
    return Estimate(tokens_in, tokens_out, cost, basis, len(usable))
