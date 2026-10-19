"""Property tests for the three most complex functions (deep review, 2026-10-19; Eric approved).

Hand-written examples check the cases someone thought of. These check rules that must hold for
every input, on many generated ones (seeded, so a failure always reproduces):

- `translation.translate` on random step graphs, cycles included: it never invents a step
  (constraint 23, rule 7), keeps the existing lines first, adds lines only between steps of the
  views it draws them in, and asks a question for every "not described" connector.
- `lint.run_lint` on random changes to the sample map: it reports exactly the missing exits and
  unreachable or dead-end steps that constraint 6 forbids, ignores rejected steps, and gives the
  same answer every time.
- `s4_assemble.assemble`, through drafts of both source mixes the mock answers were recorded
  for (everything; interview only): one start and one end, no line
  to a step that isn't on the map, every observed or inferred step on verified evidence
  (constraint 1), no recommended (R) step from the AI and no hidden name.
"""

from __future__ import annotations

import json
import random
from collections import deque
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import AppConfig
from app.domain.graph import Graph, GraphEdge, LintReport
from app.domain.sensemaking import StepPosition, TranslationEdge, TranslationStep
from app.services import lint, translation
from tests import fixture_engagement
from tests.golden.test_golden_baselines import drafted

SEEDS = range(300)
G1 = Graph.model_validate(json.loads((Path(__file__).parents[1] / "golden" / "G1_graph.json")
                                     .read_text(encoding="utf-8")))  # fmt: skip

# --- translate ----------------------------------------------------------------------------------

STATES = ["corroborated", "contested", "practiced_only", "documented_only", "not_assessed",
          "trace_contradicted"]  # fmt: skip
EDGE_KINDS = ["sequence", "sequence", "sequence", "yes", "no", "approve", "reject", "rework"]
WORDS = ["load plan", "weights", "loading report", "special loads", "final figures"]


def random_steps(rng: random.Random) -> tuple[list[TranslationStep], list[TranslationEdge]]:
    n = rng.randint(2, 12)
    steps = [TranslationStep(id="start", kind="start", label="Start", source_state="not_assessed",
                             provenance="O")]  # fmt: skip
    for i in range(n):
        positions = [StepPosition(source_id=rng.choice(["i1", "i2"]), seq=rng.randint(1, 40),
                                  lived=rng.random() < 0.5, explicit=rng.random() < 0.3)
                     for _ in range(rng.randint(0, 2))]  # fmt: skip
        documents = [StepPosition(source_id="d1", seq=rng.randint(1, 40))
                     for _ in range(rng.randint(0, 1))]  # fmt: skip
        steps.append(TranslationStep(
            id=f"s{i}", kind=rng.choice(["activity", "activity", "decision", "approval"]),
            label=f"Step {i}", source_state=rng.choice(STATES),
            provenance=rng.choice(["O", "O", "I", "R"]), interview=positions, documents=documents,
            lane=rng.choice(["Lead", "Controller", "Ramp"]),
            gives=rng.sample(WORDS, rng.randint(0, 1)), takes=rng.sample(WORDS, rng.randint(0, 1)),
        ))  # fmt: skip
    steps.append(TranslationStep(id="end", kind="end", label="End", source_state="not_assessed",
                                 provenance="O"))  # fmt: skip
    ids = [s.id for s in steps]
    pairs: set[tuple[str, str]] = set()
    for _ in range(rng.randint(1, 2 * n + 2)):
        a, b = rng.choice(ids[:-1]), rng.choice(ids[1:])
        if a != b:
            pairs.add((a, b))
    edges = [TranslationEdge(id=f"e{k}", from_id=a, to_id=b, kind=rng.choice(EDGE_KINDS),
                             label=rng.choice(["", "", "Yes", "No"]))
             for k, (a, b) in enumerate(sorted(pairs))]  # fmt: skip
    return steps, edges


def views_of(membership: str) -> set[str]:
    return {"both": {"done", "documented"}, "done_only": {"done"},
            "documented_only": {"documented"}}[membership]  # fmt: skip


@pytest.mark.parametrize("seed", SEEDS)
def test_translate_never_invents_a_step_and_keeps_each_line_in_its_views(seed: int) -> None:
    rng = random.Random(seed)
    steps, edges = random_steps(rng)
    ids = {s.id for s in steps}
    result = translation.translate(steps, edges)
    assert result == translation.translate(steps, edges)  # the same answer every time
    assert set(result.element_views) == ids
    for s in steps:
        assert result.element_views[s.id] == translation.element_view(s)
    # The existing lines come first, unchanged.
    for given, out in zip(edges, result.edges, strict=False):
        assert (out.from_id, out.to_id, out.kind, out.label) == (
            given.from_id, given.to_id, given.kind, given.label)  # fmt: skip
    added = result.edges[len(edges) :]
    seen: dict[str, set[tuple[str, str]]] = {"done": set(), "documented": set()}
    for e in result.edges[: len(edges)]:
        for view in views_of(e.view_membership):
            seen[view].add((e.from_id, e.to_id))
    for e in added:
        assert e.from_id in ids and e.to_id in ids, "a line to a step that isn't there"
        assert e.from_id != e.to_id
        assert e.kind not in translation.BACKWARD
        for view in views_of(e.view_membership):
            for end in (e.from_id, e.to_id):
                assert view in views_of(result.element_views[end]), (seed, e, view)
            assert (e.from_id, e.to_id) not in seen[view], ("a line drawn twice", seed, e)
            seen[view].add((e.from_id, e.to_id))
        if e.kind == "gap":
            assert e.view_membership == "done_only" and e.label == translation.NOT_DESCRIBED
            assert any(q.reason == "not_described" and q.element_id == e.to_id
                       for q in result.questions)  # fmt: skip
    for q in result.questions:
        assert q.element_id in ids


# --- run_lint -----------------------------------------------------------------------------------


def mutate(rng: random.Random, graph: Graph) -> Graph:
    """Up to six random changes a review or a refresh could make: lines dropped, added or left
    unlabelled, steps rejected or changed in kind."""
    g = graph.model_copy(deep=True)
    steps = [e for e in g.elements if e.kind not in ("start", "end")]
    for k in range(rng.randint(1, 6)):
        change = rng.randrange(5)
        if change == 0 and g.edges:
            g.edges.pop(rng.randrange(len(g.edges)))
        elif change == 1:
            a, b = rng.choice(g.elements), rng.choice(g.elements)
            g.edges.append(GraphEdge(id=f"x{k}", from_=a.id, to=b.id,
                                     kind=rng.choice(["sequence", "yes", "no", "approve",
                                                      "reject", "rework"]),
                                     label=rng.choice(["", "Yes", "No"])))  # fmt: skip
        elif change == 2:
            rng.choice(steps).review_status = "rejected"
        elif change == 3:
            rng.choice(steps).kind = rng.choice(["activity", "decision", "approval"])
        elif change == 4 and g.edges:
            rng.choice(g.edges).label = ""
    return g


def expected_structure(g: Graph) -> set[tuple[str, str | None]]:
    """Constraint 6, worked out independently: every decision has two labelled exits, every
    approval an approve and a reject or rework exit, every element but the end a way out, every
    element a way in from the one start. Rejected steps and their lines don't count."""
    live = {e.id: e for e in g.elements if e.review_status != "rejected"}
    lines = [e for e in g.edges if e.from_ in live and e.to in live]
    found: set[tuple[str, str | None]] = set()
    for e in live.values():
        out = [x for x in lines if x.from_ == e.id]
        if e.kind == "decision" and len([x for x in out if x.label.strip()]) < 2:
            found.add(("L4", e.id))
        kinds = {x.kind for x in out}
        if e.kind == "approval" and ("approve" not in kinds or not kinds & {"reject", "rework"}):
            found.add(("L5", e.id))
        if e.kind != "end" and not out:
            found.add(("L9", e.id))
    starts = [e for e in live.values() if e.kind == "start"]
    if len(starts) != 1:
        found.add(("L9", None))
    else:
        reached, todo = {starts[0].id}, deque([starts[0].id])
        while todo:
            node = todo.popleft()
            for x in lines:
                if x.from_ == node and x.to not in reached:
                    reached.add(x.to)
                    todo.append(x.to)
        found |= {("L9", e) for e in live if e not in reached}
    return found


def structural(report: LintReport) -> set[tuple[str, str | None]]:
    """L4, L5 and the element-level L9 failures of the main map (not the per-view checks)."""
    return {(i.rule, i.element_id) for i in report.failures
            if i.rule in ("L4", "L5", "L9") and i.view is None}  # fmt: skip


def test_the_sample_map_passes_the_structure_rules() -> None:
    assert structural(lint.run_lint(G1)) == expected_structure(G1) == set()


@pytest.mark.parametrize("seed", SEEDS)
def test_lint_reports_exactly_the_structure_constraint_6_forbids(seed: int) -> None:
    g = mutate(random.Random(seed), G1)
    report = lint.run_lint(g)
    assert report == lint.run_lint(g)  # the same answer every time
    assert structural(report) == expected_structure(g), seed
    rejected = {e.id for e in g.elements if e.review_status == "rejected"}
    known = {e.id for e in g.elements}
    for issue in report.failures + report.warnings:
        assert issue.element_id is None or issue.element_id in known - rejected, (seed, issue)


@pytest.mark.parametrize("seed", range(60))
def test_rejected_steps_change_nothing(seed: int) -> None:
    """Adding rejected steps, and lines to and from them, leaves the report as it was."""
    rng = random.Random(seed)
    g = mutate(rng, G1)
    before = lint.run_lint(g)
    decoys = g.model_copy(deep=True)
    for k in range(rng.randint(1, 3)):
        copy = rng.choice([e for e in g.elements if e.kind not in ("start", "end")])
        decoy = copy.model_copy(update={"id": f"rejected-{k}", "stable_key": f"rejected-{k}",
                                        "review_status": "rejected"})  # fmt: skip
        decoys.elements.append(decoy)
        other = rng.choice(g.elements).id
        decoys.edges.append(GraphEdge(id=f"r{k}a", from_=other, to=decoy.id, kind="sequence",
                                      label="Yes"))  # fmt: skip
        decoys.edges.append(GraphEdge(id=f"r{k}b", from_=decoy.id, to=other, kind="sequence",
                                      label="No"))  # fmt: skip
    assert lint.run_lint(decoys) == before, seed


# --- assemble (through real drafts, Claude mocked) ---------------------------------------------

MIXES = {
    "everything": fixture_engagement.SOURCES,
    "interview only": ["interview_transcript.txt"],
}  # mixes the mock answers were recorded for (Claude is mocked by exactly what is sent)


@pytest.fixture(params=list(MIXES), scope="module")
def assembled(request: pytest.FixtureRequest,
              tmp_path_factory: pytest.TempPathFactory) -> Iterator[Graph]:  # fmt: skip
    from app.config import load_config

    folder = tmp_path_factory.mktemp("assembled")
    config: AppConfig = load_config({"PMS_ENV_FILE": str(folder / ".env"), "MOCK_CLAUDE": "1",
                                     "DATA_DIR": str(folder / "data")})  # fmt: skip
    for client, version_id in drafted(config, MIXES[request.param]):
        yield Graph.model_validate(client.get(f"/api/versions/{version_id}/graph").json())


def test_an_assembled_map_has_one_start_one_end_and_no_loose_line(assembled: Graph) -> None:
    kinds = [e.kind for e in assembled.elements]
    assert kinds.count("start") == 1 and kinds.count("end") == 1
    ids = [e.id for e in assembled.elements]
    assert len(ids) == len(set(ids))
    assert len({e.stable_key for e in assembled.elements}) == len(ids)
    for edge in assembled.edges:
        assert edge.from_ in ids and edge.to in ids, edge
        assert edge.from_ != edge.to


def test_every_assembled_step_rests_on_verified_evidence(assembled: Graph) -> None:
    """Constraint 1: the AI never invents content, and only Eric adds a recommendation (R)."""
    for e in assembled.elements:
        if e.kind in ("start", "end"):
            continue
        assert e.provenance in ("O", "I"), (e.label, e.provenance)
        assert any(ev.verified and ev.segment_id for ev in e.evidence), e.label


def test_no_hidden_name_reaches_an_assembled_map(assembled: Graph) -> None:
    text = json.dumps(assembled.model_dump(mode="json"))
    for name in ("Priya", "Nair"):
        assert name not in text
