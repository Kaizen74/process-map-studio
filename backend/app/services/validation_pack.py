"""The validation session pack (PRD Appendix F.7, §3.12.8, criterion 75): what Eric takes to a
validation session with the SME, alongside the draft map, as Markdown.

Pure: explicit inputs (names already hidden by the caller), one Markdown text out. The pack only
asks; nothing in it judges the SME's account (non-blaming wording, contrast without evaluation).
"""

from __future__ import annotations

from app.domain.graph import Graph, GraphElement
from app.domain.sensemaking import PackContrast, ValidationPackInput

WALK = "Is this how it actually happens?"
DISSENT = (
    "Imagine this map is wrong. Where would it most likely be wrong? What's missing? What would "
    "a colleague disagree with?"
)
ASSENT = "What would make it more accurate?"
CONTRAST = "What do you make of the difference?"
PRESERVE = "Of these strengths, which must we keep?"
IMPROVE = "Of these weaknesses, which matter most?"
MAX_CONTRASTS = 3


def _line(text: str) -> str:
    return " ".join(text.split())


def render_validation_pack(data: ValidationPackInput) -> str:
    lines = [
        f"# Validation session pack: {_line(data.process)} ({data.version_label})",
        "",
        "Take this to the validation session with the draft map's As done view. Use roles, not "
        "names. Afterwards, enter what you heard as edits on the Review screen.",
        "",
        "## 1. Walk the As done view",
        "",
        f"Ask: “{WALK}”",
        "",
    ]
    if data.steps:
        lines += [f"{n}. {_line(s.label)} ({_line(s.role) or 'no role yet'})"
                  for n, s in enumerate(data.steps, start=1)]  # fmt: skip
    else:
        lines.append("The As done view has no steps yet.")
    if data.gaps:
        lines += ["", "Gaps the interviews don't describe (ask what happens in between):", ""]
        lines += [f"- Between “{_line(a)}” and “{_line(b)}”: not described"
                  for a, b in data.gaps]  # fmt: skip
    lines += [
        "",
        "## 2. Dissent round, then assent round",
        "",
        f"- Dissent: “{DISSENT}”",
        f"- Assent: “{ASSENT}”",
        "",
        "## 3. Contrast without evaluation",
        "",
    ]
    contrasts = data.contrasts[:MAX_CONTRASTS]
    if contrasts:
        lines += ["Show the As done and As documented accounts side by side, without saying which "
                  f"is right. For each, ask: “{CONTRAST}”", ""]  # fmt: skip
        for c in contrasts:
            lines += [f"- **{_line(c.step)}**",
                      f"  - As done: {_line(c.done)}",
                      f"  - As documented: {_line(c.documented)}"]  # fmt: skip
    else:
        lines.append("The two views tell the same story on this map; skip this part.")
    lines += ["", "## 4. Preserve / improve check", ""]
    if data.strengths or data.weaknesses:
        if data.strengths:
            lines += [f"Ask: “{PRESERVE}”", ""]
            lines += [f"- {_line(s)}" for s in data.strengths] + [""]
        if data.weaknesses:
            lines += [f"Ask: “{IMPROVE}”", ""]
            lines += [f"- {_line(w)}" for w in data.weaknesses] + [""]
    else:
        lines += ["The interviews named no strengths or weaknesses yet; ask: "
                  "“What should we keep no matter what? Where does it hurt most?”", ""]  # fmt: skip
    lines += ["## Open validation questions", ""]
    if data.questions:
        lines += [f"- {f'**{_line(about)}**: ' if about else ''}{_line(q)}"
                  for about, q in data.questions]  # fmt: skip
    else:
        lines.append("None open.")
    lines += ["", "---", "", f"*{data.stamp}*", ""]
    return "\n".join(lines)


# --- Choosing the contrasts (pure, from the combined graph) --------------------------------------

VARIANT_FIELDS = ("owner", "threshold", "time", "trigger")
STEP_KINDS = ("activity", "decision", "approval")


def _who(e: GraphElement, roles: dict[str, str]) -> str:
    role = roles.get(e.lane_role_id or "", "")
    return f"{e.label} ({role})" if role else e.label


def contrasts(graph: Graph) -> list[PackContrast]:
    """Up to three steps where the views differ (F.7 item 3): a step both views have but with a
    different owner, threshold, time or trigger first, then steps only the documents describe,
    then steps only the interviews describe; process order within each group."""
    roles = {r.id: r.name for r in graph.roles}
    steps = [e for e in graph.elements if e.kind in STEP_KINDS and e.review_status != "rejected"]
    differing: list[PackContrast] = []
    for e in steps:
        done = (e.variants or {}).get("done", {})
        documented = (e.variants or {}).get("documented", {})
        fields = [f for f in VARIANT_FIELDS if done.get(f) != documented.get(f)]
        if fields:
            differing.append(PackContrast(
                step=e.label,
                done="; ".join(f"{f}: {done.get(f) or 'not stated'}" for f in fields),
                documented="; ".join(f"{f}: {documented.get(f) or 'not stated'}" for f in fields),
            ))  # fmt: skip
    documents_only = [
        PackContrast(step=e.label, done="The interviews don't describe this step.",
                     documented=_who(e, roles))
        for e in steps if e.view_membership == "documented_only"
    ]  # fmt: skip
    interviews_only = [
        PackContrast(step=e.label, done=_who(e, roles),
                     documented="The documents don't describe this step.")
        for e in steps if e.view_membership == "done_only"
    ]  # fmt: skip
    return [*differing, *documents_only, *interviews_only][:MAX_CONTRASTS]
