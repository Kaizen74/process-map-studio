"""Engagement, scope-card and role actions (PRD §4, §5.4 Setup)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.actions import engagements as actions
from app.actions import settings as settings_actions
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import EngagementCreate, RoleCreate, RolePatch, ScopeFields
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import tables as t

Sessions = sessionmaker[Session]


def ok[T](result: Result[T]) -> T:
    assert isinstance(result, Ok), result
    return result.value


def err(result: Result[Any]) -> Err:
    assert isinstance(result, Err), result
    return result


def make(config: AppConfig, sessions: Sessions, **fields: Any) -> str:
    return ok(
        actions.create_engagement(config, sessions, EngagementCreate(name="Load control", **fields))
    ).id


def audit_rows(sessions: Sessions, engagement_id: str | None = None) -> list[dict[str, Any]]:
    with session_scope(sessions) as session:
        return audit.list_recent(session, engagement_id=engagement_id)


# --- Create and read ---------------------------------------------------------------------


def test_create_tidies_the_scope_card(settings_config: AppConfig, sessions: Sessions) -> None:
    view = ok(
        actions.create_engagement(
            settings_config,
            sessions,
            EngagementCreate(
                name="  Load control ",
                industry=" Aviation ground handling ",
                adjacent_industries=["Air cargo", "air cargo", " ", "Airport operations"],
                confidential_terms=["Acme Ground Services", "LC-07", "RP-02"],
            ),
        )
    )
    assert view.name == "Load control"
    assert view.industry == "Aviation ground handling"
    assert view.adjacent_industries == ["Air cargo", "Airport operations"]
    assert view.confidential_terms == ["Acme Ground Services", "LC-07", "RP-02"]
    assert view.status == "active"
    assert ok(actions.get_engagement(sessions, view.id)) == view


def test_confidential_terms_are_stored_but_not_as_name_redactions(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    engagement_id = make(settings_config, sessions, confidential_terms=["Acme Ground Services"])
    with session_scope(sessions) as session:
        rows = session.query(t.RedactionTerm).filter_by(engagement_id=engagement_id).all()
        assert [(r.term, r.origin) for r in rows] == [("Acme Ground Services", "confidential_term")]


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "x" * 121}, "name"),
        ({"name": "ok", "process_kpi": "x" * 2001}, "process_kpi"),
        ({"name": "ok", "in_scope_roles": ["x" * 121]}, "in_scope_roles"),
        ({"name": "ok", "confidential_terms": [f"t{i}" for i in range(51)]}, "confidential_terms"),
        ({"name": "ok", "adjacent_industries": ["two\nlines"]}, "adjacent_industries"),
    ],
)
def test_create_validation(
    settings_config: AppConfig, sessions: Sessions, fields: dict[str, Any], field: str
) -> None:
    result = err(actions.create_engagement(settings_config, sessions, EngagementCreate(**fields)))
    assert result.kind is ErrorKind.VALIDATION and result.details["field"] == field
    assert ok(actions.list_engagements(sessions)) == []


def test_missing_engagement(sessions: Sessions, settings_config: AppConfig) -> None:
    assert err(actions.get_engagement(sessions, "nope")).message == actions.ENGAGEMENT_MISSING
    assert (
        err(
            actions.update_engagement(settings_config, sessions, "nope", ScopeFields(trigger="x"))
        ).kind
        is ErrorKind.NOT_FOUND
    )
    assert (
        err(actions.delete_engagement(settings_config, sessions, "nope")).kind
        is ErrorKind.NOT_FOUND
    )
    assert err(actions.list_roles(sessions, "nope")).kind is ErrorKind.NOT_FOUND


def test_list_summaries_count_sources_and_review_progress(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    first = make(settings_config, sessions)
    second = ok(
        actions.create_engagement(settings_config, sessions, EngagementCreate(name="Second"))
    ).id
    with session_scope(sessions) as session:
        session.add(
            t.Source(
                engagement_id=first, kind="sop", filename="a.docx", stored_path="x", format="docx"
            )
        )
        version = t.MapVersion(engagement_id=first, label="v0.1", state="draft")
        session.add(version)
        session.flush()
        for status in ("draft", "confirmed", "edited", "draft"):
            session.add(
                t.Element(
                    version_id=version.id,
                    stable_key=status,
                    kind="activity",
                    label="s",
                    provenance="O",
                    review_status=status,
                )
            )
    items = {s.id: s for s in ok(actions.list_engagements(sessions))}
    assert items[first].sources_count == 1
    assert items[first].latest_version is not None and items[first].latest_version.label == "v0.1"
    assert (items[first].review_progress.reviewed, items[first].review_progress.total) == (2, 4)
    assert items[second].latest_version is None and items[second].sources_count == 0


# --- Update, audit, delete ---------------------------------------------------------------


def test_update_changes_only_what_was_sent_and_audits_it(
    settings_config: AppConfig, sessions: Sessions, env_file: Path
) -> None:
    env_file.write_text("OWNER_NAME=Eric Yim\n")
    engagement_id = make(settings_config, sessions, trigger="Flight scheduled")
    view = ok(
        actions.update_engagement(
            settings_config,
            sessions,
            engagement_id,
            ScopeFields(end_point="Load sheet issued", trigger="Flight scheduled"),
        )
    )
    assert (view.trigger, view.end_point) == ("Flight scheduled", "Load sheet issued")
    rows = audit_rows(sessions, engagement_id)
    assert rows[0]["action"] == "Edited process scope"
    assert rows[0]["actor"] == "Eric Yim"
    assert rows[0]["before"] == {"end_point": ""} and rows[0]["after"] == {
        "end_point": "Load sheet issued"
    }
    assert rows[-1]["action"] == "Created engagement"


def test_update_with_no_real_change_writes_no_audit_row(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    engagement_id = make(settings_config, sessions)
    ok(
        actions.update_engagement(
            settings_config, sessions, engagement_id, ScopeFields(name="Load control")
        )
    )
    assert [r["action"] for r in audit_rows(sessions, engagement_id)] == ["Created engagement"]


def test_patch_cannot_blank_a_field_with_null(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    engagement_id = make(settings_config, sessions)
    result = err(
        actions.update_engagement(settings_config, sessions, engagement_id, ScopeFields(name=None))
    )
    assert result.details["field"] == "name"


def test_delete_removes_rows_and_files(settings_config: AppConfig, sessions: Sessions) -> None:
    engagement_id = make(settings_config, sessions)
    other_id = ok(
        actions.create_engagement(settings_config, sessions, EngagementCreate(name="Other"))
    ).id
    for kind in ("sources", "images"):
        folder = settings_config.data_dir / kind / engagement_id
        folder.mkdir(parents=True)
        (folder / "file.bin").write_bytes(b"confidential")
    keep = settings_config.data_dir / "sources" / other_id
    keep.mkdir(parents=True)
    ok(
        actions.create_role(
            settings_config, sessions, engagement_id, RoleCreate(name="Load controller")
        )
    )
    assert ok(actions.delete_engagement(settings_config, sessions, engagement_id)) is None
    assert not (settings_config.data_dir / "sources" / engagement_id).exists()
    assert not (settings_config.data_dir / "images" / engagement_id).exists()
    assert keep.exists()
    assert [e.id for e in ok(actions.list_engagements(sessions))] == [other_id]
    with session_scope(sessions) as session:
        assert session.query(t.Role).count() == 0


def test_delete_reports_files_it_could_not_remove(
    settings_config: AppConfig, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    engagement_id = make(settings_config, sessions)
    (settings_config.data_dir / "sources" / engagement_id).mkdir(parents=True)
    monkeypatch.setattr("app.actions.engagements.shutil.rmtree", lambda *_a, **_k: None)
    result = err(actions.delete_engagement(settings_config, sessions, engagement_id))
    assert result.kind is ErrorKind.IO
    assert "The engagement was deleted" in result.message


# --- Roles and lanes ------------------------------------------------------------------------


def test_roles_are_added_to_the_bottom_lane(settings_config: AppConfig, sessions: Sessions) -> None:
    engagement_id = make(settings_config, sessions)
    for name in ("Load controller", "Load control lead", "Ramp"):
        ok(actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name=name)))
    roles = ok(actions.list_roles(sessions, engagement_id))
    assert [(r.name, r.lane_order) for r in roles] == [
        ("Load controller", 1),
        ("Load control lead", 2),
        ("Ramp", 3),
    ]


def test_moving_a_role_renumbers_the_lanes(settings_config: AppConfig, sessions: Sessions) -> None:
    engagement_id = make(settings_config, sessions)
    ids = [
        ok(actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name=n))).id
        for n in "ABCD"
    ]
    ok(actions.update_role(settings_config, sessions, ids[3], RolePatch(lane_order=1)))
    assert [r.name for r in ok(actions.list_roles(sessions, engagement_id))] == ["D", "A", "B", "C"]
    ok(actions.update_role(settings_config, sessions, ids[3], RolePatch(lane_order=99)))
    roles = ok(actions.list_roles(sessions, engagement_id))
    assert [(r.name, r.lane_order) for r in roles] == [("A", 1), ("B", 2), ("C", 3), ("D", 4)]


def test_role_names_are_unique_ignoring_case(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    engagement_id = make(settings_config, sessions)
    ok(actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name="Ramp")))
    other = ok(
        actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name="Captain"))
    )
    clash = err(
        actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name="ramp"))
    )
    assert (
        clash.kind is ErrorKind.CONFLICT and clash.message == "There is already a role called ramp."
    )
    rename = err(actions.update_role(settings_config, sessions, other.id, RolePatch(name="RAMP")))
    assert rename.kind is ErrorKind.CONFLICT


def test_role_edits_are_tidied_validated_and_audited(
    settings_config: AppConfig, sessions: Sessions
) -> None:
    engagement_id = make(settings_config, sessions)
    role = ok(
        actions.create_role(
            settings_config,
            sessions,
            engagement_id,
            RoleCreate(name="Load controller", aliases=["LC", "lc", " "]),
        )
    )
    assert role.aliases == ["LC"]
    edited = ok(
        actions.update_role(
            settings_config,
            sessions,
            role.id,
            RolePatch(name=" Load controller (widebody) ", is_system=True),
        )
    )
    assert (edited.name, edited.is_system) == ("Load controller (widebody)", True)
    assert (
        err(
            actions.update_role(settings_config, sessions, role.id, RolePatch(lane_order=0))
        ).details["field"]
        == "lane_order"
    )
    assert (
        err(actions.update_role(settings_config, sessions, role.id, RolePatch(name=""))).details[
            "field"
        ]
        == "name"
    )
    assert (
        err(
            actions.update_role(settings_config, sessions, role.id, RolePatch(aliases=["x" * 81]))
        ).details["field"]
        == "aliases"
    )
    assert (
        err(
            actions.create_role(settings_config, sessions, engagement_id, RoleCreate(name="x" * 81))
        ).details["field"]
        == "name"
    )
    assert (
        err(
            actions.create_role(
                settings_config, sessions, engagement_id, RoleCreate(name="ok", aliases=["a\nb"])
            )
        ).details["field"]
        == "aliases"
    )
    assert (
        err(actions.update_role(settings_config, sessions, "nope", RolePatch(name="x"))).message
        == actions.ROLE_MISSING
    )
    assert (
        err(actions.create_role(settings_config, sessions, "nope", RoleCreate(name="x"))).kind
        is ErrorKind.NOT_FOUND
    )
    actions_logged = [r["action"] for r in audit_rows(sessions, engagement_id)]
    assert actions_logged[:2] == ["Edited role", "Added role"]


def test_model_change_writes_an_audit_row(settings_config: AppConfig, sessions: Sessions) -> None:
    ok(
        settings_actions.update_model(
            settings_config, "claude-sonnet-5", "medium", False, sessions=sessions
        )
    )
    row = audit_rows(sessions)[0]
    assert row["action"] == "Changed model settings" and row["target_type"] == "settings"
    assert row["before"]["model"] == "claude-opus-5-5"
    assert row["after"] == {
        "model": "claude-sonnet-5",
        "effort": "medium",
        "verifier_enabled": False,
    }
