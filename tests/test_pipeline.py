"""Smoke test for the current 5-agent pipeline.

Mocks the OpenAI client so the test doesn't hit the network or spend tokens.
Verifies:
  - run_initial yields 6 progressive states ending with all panels populated
  - run_followup re-runs the targeted agent and cascades through downstream agents
  - Store fallback (in-memory mode) records conversation + turns correctly

Run with:  uv run pytest tests/ -v
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from backend import store


# ─── Fake OpenAI client ─────────────────────────────────────────────────────

# Each agent is identified by a fragment of its system prompt; the fake
# returns a deterministic payload per agent so the pipeline can run end-to-end
# without hitting OpenAI.
_FAKE_RESPONSES = {
    "plaintiff's attorney":  "PLAINTIFF: strong argument for breach of contract.",
    "defense attorney":      "DEFENSE: contract was void ab initio.",
    "legal expert":          json.dumps({
        "key_legal_questions":   ["Was there valid offer and acceptance?"],
        "applicable_law":        "Restatement (Second) of Contracts §17.",
        "precedents":            "Lucy v. Zehmer.",
        "burden_of_proof":       "Plaintiff must prove existence of contract by preponderance.",
        "critical_risk_factors": ["Statute of frauds applicability"],
    }),
    "judge":                 json.dumps({
        "final_verdict":             "Judgment for the plaintiff on the breach of contract claim.",
        "stronger_position":         "Plaintiff",
        "judicial_assessment":       "Plaintiff has the stronger position.",
        "plaintiff_vulnerabilities": ["Documentation gaps"],
        "defense_vulnerabilities":   ["Weak procedural arguments"],
        "scores": [
            {"criterion": "Legal theory strength", "plaintiff": 8, "defense": 5,
             "notes": "Plaintiff's theory is well-grounded."},
        ],
    }),
    "legal strategist":      "STRATEGY: gather documentation and pursue settlement.",
}


def _fake_create(**kwargs):
    """Return a stub completion routed by the system prompt."""
    system_msg = next(
        (m["content"] for m in kwargs["messages"] if m["role"] == "system"), ""
    ).lower()

    text = "[unmocked agent]"
    for marker, payload in _FAKE_RESPONSES.items():
        if marker in system_msg:
            text = payload
            break

    return MagicMock(choices=[MagicMock(message=MagicMock(content=text))])


@pytest.fixture(autouse=True)
def _mock_openai(monkeypatch):
    """Patch the OpenAI client used by the LLMAdapter for every test."""
    # Import inside fixture so the env-var-required imports don't run before
    # we set them.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setenv("CLERK_JWKS_URL", "")  # auth bypassed
    monkeypatch.setenv("DDB_TABLE", "")        # in-memory store

    # Reset the OpenAI client singleton so re-import picks up the patched env
    from backend import adapter
    adapter._client = None

    # Patch the create method on whatever client gets built next
    fake_client = MagicMock()
    fake_client.chat.completions.create = MagicMock(side_effect=_fake_create)

    def _get_fake_client():
        return fake_client

    monkeypatch.setattr(adapter, "_get_client", _get_fake_client)
    yield


# ─── Tests ──────────────────────────────────────────────────────────────────

def _drain(gen):
    """Run a generator to completion, returning (yields, final_state)."""
    yields = []
    final = None
    while True:
        try:
            yields.append(next(gen))
        except StopIteration as stop:
            final = stop.value
            break
    return yields, final


def test_run_initial_runs_only_three_agents():
    """Phase 1: only Plaintiff/Defense/Expert run. Judge/Strategist panels
    show placeholder text until final judgment is pronounced."""
    from backend.pipeline import run_initial, JUDGE_PLACEHOLDER, STRATEGY_PLACEHOLDER

    yields, final = _drain(run_initial(
        "contract dispute over $50k delivery", "Contract Law",
        "I am the plaintiff seeking damages", "United Kingdom",
    ))

    # 4 yields: 3 progressive (one per agent starting) + 1 final summary
    assert len(yields) == 4, f"expected 4 yields, got {len(yields)}"

    p_md, d_md, e_md, j_md, rows, s_md, summary = yields[-1]
    assert "PLAINTIFF" in p_md
    assert "DEFENSE" in d_md
    assert "Restatement" in e_md
    assert j_md == JUDGE_PLACEHOLDER
    assert rows == []
    assert s_md == STRATEGY_PLACEHOLDER
    assert "final judgment" in summary.lower()

    # Final state dict has only P/D/E
    assert set(final["agents"]) == {"plaintiff", "defense", "expert"}


def test_run_final_judgment_completes_the_package():
    """Phase 2: Judge + Strategist run using prev_turn's P/D/E outputs."""
    from backend.pipeline import run_initial, run_final_judgment

    _, prev_turn = _drain(run_initial("breach", "Contract Law", "plaintiff", "United Kingdom"))
    yields, final = _drain(run_final_judgment(prev_turn))

    # 3 yields: judge starting, strategist starting, final
    assert len(yields) == 3
    p_md, d_md, e_md, j_md, rows, s_md, summary = yields[-1]
    assert "Plaintiff" in j_md
    assert len(rows) == 1
    assert "STRATEGY" in s_md
    assert "Stronger Position" in summary

    assert set(final["agents"]) == {"plaintiff", "defense", "expert", "judge", "strategist"}


def test_run_final_judgment_refuses_without_phase1():
    from backend.pipeline import run_final_judgment

    gen = run_final_judgment({"agents": {}, "case_description": "",
                              "legal_area": "", "user_position": ""})
    with pytest.raises(Exception, match="missing agent"):
        next(gen)


def test_followup_before_judgment_does_not_invoke_judge_or_strategist():
    """Refining plaintiff before final judgment should cascade through
    defense + expert only — judge/strategist stay as placeholders."""
    from backend.pipeline import (
        run_initial, run_followup, JUDGE_PLACEHOLDER, STRATEGY_PLACEHOLDER,
    )

    _, prev_turn = _drain(run_initial("breach", "Contract Law", "plaintiff", "United Kingdom"))
    yields, new_turn = _drain(run_followup(prev_turn, "plaintiff",
                                           "consider the new email evidence"))

    # Final yield: judge/strategist still placeholders
    p_md, d_md, e_md, j_md, rows, s_md, summary = yields[-1]
    assert j_md == JUDGE_PLACEHOLDER
    assert rows == []
    assert s_md == STRATEGY_PLACEHOLDER

    # Agents dict has only P/D/E
    assert set(new_turn["agents"]) == {"plaintiff", "defense", "expert"}


def test_followup_judge_blocked_before_final_judgment():
    """Trying to refine the judge before phase 2 should raise."""
    from backend.pipeline import run_initial, run_followup

    _, prev_turn = _drain(run_initial("breach", "Contract Law", "plaintiff", "United Kingdom"))
    gen = run_followup(prev_turn, "judge", "be tougher on the defense")
    with pytest.raises(Exception, match="before final judgment"):
        next(gen)


def test_followup_after_judgment_cascades_through_judge_and_strategist():
    from backend.pipeline import run_initial, run_final_judgment, run_followup

    _, t1 = _drain(run_initial("breach", "Contract Law", "plaintiff", "United Kingdom"))
    _, t2 = _drain(run_final_judgment(t1))
    yields, t3 = _drain(run_followup(t2, "plaintiff", "new email evidence"))

    # All 5 agents present in final state, judge/strategist re-ran
    assert set(t3["agents"]) == {"plaintiff", "defense", "expert", "judge", "strategist"}
    p_md, d_md, e_md, j_md, rows, s_md, summary = yields[-1]
    assert "Plaintiff" in j_md
    assert len(rows) == 1
    assert "STRATEGY" in s_md


def test_store_inmemory_round_trip(monkeypatch):
    """In-memory fallback should accept create + append + list + load."""
    # Force in-memory mode regardless of what's in .env. settings.* are already
    # bound at import time, so we patch the store module's symbols directly.
    monkeypatch.setattr(store, "STORE_BACKEND", "memory")
    store._mem.clear()

    user_id = "user-test-1"
    conv_id = store.create_conversation(
        user_id,
        title="Test case",
        legal_area="Contract Law",
        case_description="full case text",
        user_position="plaintiff",
    )
    assert conv_id

    n = store.append_turn(user_id, conv_id, {
        "case_description": "full case text",
        "legal_area": "Contract Law",
        "user_position": "plaintiff",
        "agents": {"plaintiff": "p", "defense": "d", "expert": {}, "judge": {}, "strategist": "s"},
    })
    assert n == 1

    convs = store.list_conversations(user_id)
    assert len(convs) == 1
    assert convs[0]["title"] == "Test case"

    loaded = store.load_conversation(user_id, conv_id)
    assert loaded is not None
    assert loaded["header"]["legal_area"] == "Contract Law"
    assert len(loaded["turns"]) == 1


def test_store_sqlite_round_trip(monkeypatch, tmp_path):
    """SQLite backend creates the file, persists turns, returns them on load."""
    db_path = tmp_path / "moootcourt.sqlite"
    monkeypatch.setattr(store, "STORE_BACKEND", "sqlite")
    monkeypatch.setattr(store, "SQLITE_PATH", str(db_path))
    monkeypatch.setattr(store, "_sqlite_conn", None)  # force re-init for this test

    user_id = "user-sqlite-1"
    conv_id = store.create_conversation(
        user_id,
        title="SQLite case",
        legal_area="Employment Law",
        case_description="alleged wrongful termination",
        user_position="employee",
    )
    assert conv_id
    assert db_path.exists(), "SQLite file should be created on first call"

    n1 = store.append_turn(user_id, conv_id, {
        "case_description": "alleged wrongful termination",
        "legal_area": "Employment Law",
        "user_position": "employee",
        "agents": {"plaintiff": "p", "defense": "d", "expert": {"key": "v"}},
    })
    n2 = store.append_turn(user_id, conv_id, {
        "case_description": "alleged wrongful termination",
        "legal_area": "Employment Law",
        "user_position": "employee",
        "agents": {"plaintiff": "p2", "defense": "d2", "expert": {}},
        "follow_up": {"target": "plaintiff", "text": "consider new evidence"},
    })
    assert n1 == 1 and n2 == 2

    convs = store.list_conversations(user_id)
    assert len(convs) == 1
    assert convs[0]["title"] == "SQLite case"
    assert convs[0]["turn_count"] == 2

    loaded = store.load_conversation(user_id, conv_id)
    assert loaded is not None
    assert loaded["header"]["legal_area"] == "Employment Law"
    assert len(loaded["turns"]) == 2
    # Turns deserialise their JSON-encoded agents back into dicts
    assert loaded["turns"][0]["agents"]["plaintiff"] == "p"
    assert loaded["turns"][1]["follow_up"]["target"] == "plaintiff"

    # Reopen connection — data must survive across "restart"
    monkeypatch.setattr(store, "_sqlite_conn", None)
    convs2 = store.list_conversations(user_id)
    assert len(convs2) == 1 and convs2[0]["conversation_id"] == conv_id
