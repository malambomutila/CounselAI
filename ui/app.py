"""Gradio Blocks UI for CounselAI.

Layout:
  ┌───────────────┬──────────────────────────────────────────────┐
  │ Sidebar       │ Main analysis pane                           │
  │ (history)     │                                              │
  │ - new case    │   Inputs row (case / area / position)        │
  │ - past convs  │   Run button                                 │
  │   click to    │   Summary                                    │
  │   load        │   Plaintiff | Defense panels (with follow-up)│
  │               │   Expert | Judge panels (with follow-up)     │
  │               │   Strategy memo (with follow-up) | Scores    │
  └───────────────┴──────────────────────────────────────────────┘

Per-agent follow-up: each panel has a small text box + "Refine" button.
Submitting fires `run_followup`, which re-runs the targeted agent then
cascades through downstream agents. Result becomes a new turn under the
same conversation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional, Tuple

import gradio as gr

from backend.auth import AuthError, user_id_from_request
from backend.pipeline import run_initial, run_followup
from backend.prompts import LEGAL_AREAS
from backend import store
from ui.theme import THEME, CUSTOM_CSS

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _safe_user(request: gr.Request) -> Optional[str]:
    """Return user_id or None. Logs auth failures but doesn't crash the UI."""
    try:
        return user_id_from_request(request)
    except AuthError as e:
        logger.warning("auth failed: %s", e)
        return None


def _no_auth_block() -> Tuple[str, str, str, str, list, str, str]:
    msg = "**Not signed in.** Please [sign in](/) to use CounselAI."
    return (msg, "", "", "", [], "", "")


def _format_history(items: List[Dict]) -> List[List[str]]:
    """Sidebar dataframe rows: [conv_id, title, area, last_updated]."""
    return [
        [it.get("conversation_id", ""),
         it.get("title", "")[:60],
         it.get("legal_area", ""),
         (it.get("updated_at") or "")[:10]]
        for it in items
    ]


# ── Handlers ───────────────────────────────────────────────────────────────

def handle_new(
    case: str,
    area: str,
    position: str,
    request: gr.Request,
):
    """Called when user clicks Analyse My Case. Streams pipeline output and
    persists a new conversation + turn 1 at the end."""
    user_id = _safe_user(request)
    if user_id is None:
        yield (*_no_auth_block(), "", gr.update())
        return

    last: Optional[Dict] = None
    final_state: Optional[Dict] = None
    gen = run_initial(case, area, position)
    while True:
        try:
            update = next(gen)
            last = update
            yield (*update, "", gr.update())  # active_conv unchanged
        except StopIteration as stop:
            final_state = stop.value
            break

    if final_state and last:
        # Persist conversation + first turn
        title = (case[:60] + "…") if len(case) > 60 else case
        try:
            conv_id = store.create_conversation(
                user_id,
                title=title,
                legal_area=area,
                case_description=case,
                user_position=position,
            )
            store.append_turn(user_id, conv_id, final_state)
        except Exception:
            logger.exception("failed to persist conversation")
            conv_id = ""
        yield (*last, conv_id, _refresh_history(user_id))


def handle_followup(
    target: str,
    follow_up_text: str,
    active_conv: str,
    case: str,
    area: str,
    position: str,
    p_arg: str,
    d_arg: str,
    expert_md: str,
    judge_md: str,
    score_rows_in: List,
    strategy_md: str,
    summary_md: str,
    request: gr.Request,
):
    """Called from any of the five 'Refine' buttons. Reconstructs the
    previous-turn dict from current panel state, then runs cascade re-runs."""
    user_id = _safe_user(request)
    if user_id is None:
        yield (*_no_auth_block(), active_conv, gr.update())
        return

    if not follow_up_text.strip():
        yield (p_arg, d_arg, expert_md, judge_md, score_rows_in, strategy_md, summary_md,
               active_conv, gr.update())
        return

    # We don't have full agent objects in panel state, only formatted markdown.
    # For follow-up we need the structured dicts for expert/judge. The cleanest
    # path is to load the latest turn from the store (single round trip).
    convo = store.load_conversation(user_id, active_conv) if active_conv else None
    if not convo or not convo.get("turns"):
        # No conversation context — cannot follow up. Surface a soft error.
        yield (p_arg, d_arg, expert_md, judge_md, score_rows_in,
               "_Follow-up requires a saved conversation. Run an initial case first._",
               summary_md, active_conv, gr.update())
        return

    prev_turn = convo["turns"][-1]

    last = None
    final_state = None
    try:
        gen = run_followup(prev_turn, target, follow_up_text)
    except ValueError as e:
        yield (p_arg, d_arg, expert_md, judge_md, score_rows_in,
               f"_{e}_", summary_md, active_conv, gr.update())
        return

    while True:
        try:
            update = next(gen)
            last = update
            yield (*update, active_conv, gr.update())
        except StopIteration as stop:
            final_state = stop.value
            break

    if final_state and last:
        try:
            store.append_turn(user_id, active_conv, final_state)
        except Exception:
            logger.exception("failed to persist follow-up turn")
        yield (*last, active_conv, _refresh_history(user_id))


def handle_load(
    selection: List[List[str]],
    request: gr.Request,
):
    """User clicked a row in the history dataframe. Load that conversation
    and render its latest turn into all panels."""
    user_id = _safe_user(request)
    if user_id is None:
        return (*_no_auth_block(), "", "", "", "", gr.update())

    if not selection:
        return ("", "", "", "", [], "", "", "", "", "", "", gr.update())

    conv_id = selection[0][0] if isinstance(selection[0], list) else selection[0]
    convo = store.load_conversation(user_id, conv_id)
    if not convo or not convo.get("turns"):
        return ("", "", "", "", [], "", "", "", "", "", "", gr.update())

    header = convo.get("header") or {}
    last_turn = convo["turns"][-1]
    agents = last_turn.get("agents") or {}

    from backend.formatting import format_expert, format_judge, score_rows, overall_summary
    p_md = agents.get("plaintiff", "")
    d_md = agents.get("defense", "")
    e_md = format_expert(agents.get("expert", {})) if agents.get("expert") else ""
    j_md = format_judge(agents.get("judge", {})) if agents.get("judge") else ""
    rows = score_rows(agents.get("judge", {})) if agents.get("judge") else []
    s_md = agents.get("strategist", "")
    sum_md = overall_summary(agents.get("judge", {})) if agents.get("judge") else ""

    return (
        p_md, d_md, e_md, j_md, rows, s_md, sum_md,
        header.get("case_description", ""),
        header.get("legal_area", "Contract Law"),
        header.get("user_position", ""),
        conv_id,
        gr.update(),  # history unchanged
    )


def _refresh_history(user_id: str):
    return gr.update(value=_format_history(store.list_conversations(user_id)))


def handle_load_history(request: gr.Request):
    """Initial load — populate the history sidebar."""
    user_id = _safe_user(request)
    if user_id is None:
        return gr.update(value=[])
    return _refresh_history(user_id)


# ── Layout ─────────────────────────────────────────────────────────────────

def build_demo() -> gr.Blocks:
    with gr.Blocks(
        title="CounselAI",
        fill_width=True,
        theme=THEME,
        css=CUSTOM_CSS,
    ) as demo:

        # State that survives across handler calls in the same session
        active_conv = gr.State("")

        with gr.Row():
            # ─── Sidebar ──────────────────────────────────────────────
            with gr.Column(scale=1, elem_id="sidebar", min_width=260):
                gr.Markdown("### Past cases")
                history_table = gr.Dataframe(
                    headers=["id", "Title", "Area", "Date"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    row_count=(0, "dynamic"),
                    col_count=(4, "fixed"),
                )
                refresh_btn = gr.Button("Refresh", size="sm")
                gr.Markdown("---")
                new_btn = gr.Button("➕  New case", size="sm")

            # ─── Main pane ────────────────────────────────────────────
            with gr.Column(scale=4):
                gr.Markdown(
                    "# Legal Counsel Agents\n"
                    "*Five AI legal specialists analyse your case from every "
                    "angle so you walk into proceedings fully prepared.*"
                )

                with gr.Row():
                    with gr.Column(scale=2):
                        case_input = gr.Textbox(
                            label="Case Description",
                            placeholder=(
                                "Describe the facts of your case in as much detail "
                                "as possible. Include key dates, parties involved, "
                                "actions taken, and any relevant documents..."
                            ),
                            lines=7,
                        )
                    with gr.Column(scale=1):
                        legal_area_input = gr.Dropdown(
                            label="Legal Area",
                            choices=LEGAL_AREAS,
                            value="Contract Law",
                        )
                        position_input = gr.Textbox(
                            label="Your Position",
                            placeholder=(
                                "e.g. 'I am the plaintiff seeking damages for breach "
                                "of contract'"
                            ),
                            lines=4,
                        )

                run_button = gr.Button("Analyse My Case", variant="primary", size="lg")

                gr.Markdown("---")
                summary_md = gr.Markdown("")
                gr.Markdown("---")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Plaintiff's Counsel")
                        plaintiff_out = gr.Markdown(
                            "Argument will appear here...", elem_id="plaintiff-panel"
                        )
                        with gr.Accordion("Refine plaintiff", open=False):
                            plaintiff_followup = gr.Textbox(
                                placeholder="e.g. 'Try a different theory based on consumer protection law…'",
                                lines=2,
                                show_label=False,
                            )
                            plaintiff_btn = gr.Button("Refine", size="sm")
                    with gr.Column():
                        gr.Markdown("### Defense Counsel")
                        defense_out = gr.Markdown(
                            "Counter-argument will appear here...", elem_id="defense-panel"
                        )
                        with gr.Accordion("Refine defense", open=False):
                            defense_followup = gr.Textbox(
                                placeholder="e.g. 'Focus on procedural challenges…'",
                                lines=2,
                                show_label=False,
                            )
                            defense_btn = gr.Button("Refine", size="sm")

                gr.Markdown("---")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Expert Witness Analysis")
                        expert_out = gr.Markdown(
                            "Legal analysis will appear here...", elem_id="expert-panel"
                        )
                        with gr.Accordion("Refine expert", open=False):
                            expert_followup = gr.Textbox(
                                placeholder="e.g. 'Consider the GDPR implications…'",
                                lines=2,
                                show_label=False,
                            )
                            expert_btn = gr.Button("Refine", size="sm")
                    with gr.Column():
                        gr.Markdown("### Judge's Assessment")
                        judge_out = gr.Markdown(
                            "Judicial evaluation will appear here...", elem_id="judge-panel"
                        )
                        with gr.Accordion("Refine judge", open=False):
                            judge_followup = gr.Textbox(
                                placeholder="e.g. 'Re-evaluate considering the new facts…'",
                                lines=2,
                                show_label=False,
                            )
                            judge_btn = gr.Button("Refine", size="sm")

                gr.Markdown("---")

                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### Strategic Case Memo")
                        strategy_out = gr.Markdown(
                            "Your preparation memo will appear here...",
                            elem_id="strategy-panel",
                        )
                        with gr.Accordion("Refine strategy", open=False):
                            strategy_followup = gr.Textbox(
                                placeholder="e.g. 'Prioritise settlement over trial…'",
                                lines=2,
                                show_label=False,
                            )
                            strategy_btn = gr.Button("Refine", size="sm")
                    with gr.Column(scale=1):
                        gr.Markdown("### Argument Scores")
                        score_table = gr.Dataframe(
                            headers=["Criterion", "Plaintiff", "Defense", "Notes"],
                            datatype=["str", "number", "number", "str"],
                            interactive=False,
                        )

                gr.Markdown(
                    "*This tool is for legal research and preparation purposes "
                    "only. It does not constitute legal advice. Always consult "
                    "a qualified attorney.*"
                )

        # ── Wiring ────────────────────────────────────────────────────
        outputs_main = [
            plaintiff_out, defense_out, expert_out, judge_out,
            score_table, strategy_out, summary_md,
        ]

        run_button.click(
            fn=handle_new,
            inputs=[case_input, legal_area_input, position_input],
            outputs=outputs_main + [active_conv, history_table],
            queue=True,
        )

        # Each follow-up button binds to the same handler with a different `target`
        for btn, fup_box, agent_key in [
            (plaintiff_btn, plaintiff_followup, "plaintiff"),
            (defense_btn,   defense_followup,   "defense"),
            (expert_btn,    expert_followup,    "expert"),
            (judge_btn,     judge_followup,     "judge"),
            (strategy_btn,  strategy_followup,  "strategist"),
        ]:
            btn.click(
                fn=lambda fup, conv, c, a, p, parg, darg, em, jm, sr, sm, smd, agent=agent_key:
                    handle_followup(agent, fup, conv, c, a, p, parg, darg, em, jm, sr, sm, smd),
                inputs=[
                    fup_box, active_conv,
                    case_input, legal_area_input, position_input,
                    plaintiff_out, defense_out, expert_out, judge_out, score_table,
                    strategy_out, summary_md,
                ],
                outputs=outputs_main + [active_conv, history_table],
                queue=True,
            )

        # History sidebar
        history_table.select(
            fn=handle_load,
            inputs=[history_table],
            outputs=[
                plaintiff_out, defense_out, expert_out, judge_out,
                score_table, strategy_out, summary_md,
                case_input, legal_area_input, position_input, active_conv,
                history_table,
            ],
        )
        refresh_btn.click(fn=handle_load_history, inputs=None, outputs=[history_table])
        new_btn.click(
            fn=lambda: ("", "Contract Law", "", "", "", "", "", [], "", "", "", ""),
            inputs=None,
            outputs=[
                case_input, legal_area_input, position_input,
                plaintiff_out, defense_out, expert_out, judge_out,
                score_table, strategy_out, summary_md, active_conv, summary_md,
            ],
        )

        # Populate sidebar on initial load
        demo.load(fn=handle_load_history, inputs=None, outputs=[history_table])

    return demo
