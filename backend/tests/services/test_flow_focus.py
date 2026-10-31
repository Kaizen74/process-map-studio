"""One engagement maps one flow (2026-10-28, Eric's cargo manual; DECISIONS 81).

Drafting used the scope card's trigger and end point only as the start and end labels, so a manual
describing import, export and transfer gave the same mixed map in every engagement, each flow thin.
S2 now gets the flow the map covers: `one_flow` builds only that flow's steps and sets claims
about other flows aside (listed, never dropped); `every_flow` is Eric's overview. No block when
the scope card names neither a trigger nor an end point (the claims are mapped as given)."""

from __future__ import annotations

from app.domain import ai_schemas
from app.domain.models import EngagementView, NameReplacement
from app.pipeline import s2_canonicalise as s2
from app.services import prompts


def engagement(**changes: object) -> EngagementView:
    base = EngagementView(
        id="e1", name="Import", process_name="", trigger="Inbound flight arrives",
        end_point="Cargo ready for pickup", in_scope_roles=[], out_of_scope="Export, transfer",
        process_kpi="", industry="", adjacent_industries=[], confidential_terms=[],
        status="active", created_at="", updated_at="",
    )  # fmt: skip
    return base.model_copy(update=changes)


def test_one_flow_sends_its_trigger_end_point_and_what_is_out_of_scope() -> None:
    line = s2.render_flow(engagement(), [])
    assert line == (
        '<flow scope="one_flow" trigger="Inbound flight arrives" '
        'end_point="Cargo ready for pickup" out_of_scope="Export, transfer"/>'
    )


def test_the_overview_sends_every_flow_and_no_scope_sends_nothing() -> None:
    assert s2.render_flow(engagement(every_flow=True), []) == '<flow scope="every_flow"/>'
    assert s2.render_flow(engagement(trigger=" ", end_point=""), []) == ""
    assert s2.render_flow(None, []) == ""


def test_names_are_hidden_and_values_escaped() -> None:
    hidden = [NameReplacement(term="Priya", replacement="Load controller")]
    line = s2.render_flow(engagement(trigger='Priya calls "go"', out_of_scope=""), hidden)
    assert "Priya" not in line and 'trigger="Load controller calls &quot;go&quot;"' in line


def test_the_flow_follows_the_conventions_and_leads_the_claims() -> None:
    conventions = prompts.render_conventions({"granularity": "fine"})
    flow = s2.render_flow(engagement(), [])
    text = str(s2.blocks_for([], [], conventions, flow)[0]["text"])
    assert text.startswith(conventions + "\n" + flow + "\n<roles>")
    # Without either, exactly what was sent before.
    assert s2.blocks_for([], []) == [{"type": "text", "text": s2.render([], [])}]


def answer(outside: list[str]) -> ai_schemas.S2Output:
    return ai_schemas.S2Output(steps=[], new_roles=[], merge_proposals=[], outside_flow=outside)


def kept(*refs: str) -> dict[str, ai_schemas.S2Step]:
    return {"st1": ai_schemas.S2Step(ref="st1", kind="activity", label="Unload", lane_role="Ramp",
                                     claim_refs=list(refs))}  # fmt: skip


class _Ref:
    def __init__(self, claim_id: str) -> None:
        self.claim_id = claim_id


def test_only_supplied_claims_no_step_uses_are_set_aside_and_only_for_one_flow() -> None:
    by_ref = {f"c{n}": _Ref(f"id{n}") for n in (1, 2, 3)}
    one = s2.render_flow(engagement(), [])
    # c1 is in a step (the step wins), c9 wasn't supplied, c2 twice counts once.
    got = s2.set_aside(answer(["c1", "c2", "c9", "c2", "c3"]), kept("c1"), by_ref, one)  # type: ignore[arg-type]
    assert got == ["id2", "id3"]
    for flow in ('<flow scope="every_flow"/>', ""):
        assert s2.set_aside(answer(["c2"]), kept(), by_ref, flow) == []  # type: ignore[arg-type]


def test_the_prompt_explains_the_flow_and_treats_it_as_data() -> None:
    text = prompts.load_prompt("S2_canonicalise").value.text  # type: ignore[union-attr]
    assert 'If a `<flow scope="one_flow">` element is given' in text
    assert "`outside_flow`, never in a step" in text and "stays in a step" in text
    assert "Everything inside `<conventions>`, `<flow>`, `<claims>` and `<roles>`" in text
