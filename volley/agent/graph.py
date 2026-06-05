from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from volley.agent.state import VolleyState
from volley.agent.nodes import extract_fields, classify, retrieve_tone, draft_reply, skip
from volley.agent.routing import route_after_classify
from volley.config import CHROMA_DB_PATH

import os

CHECKPOINT_DB = os.path.join(os.path.dirname(CHROMA_DB_PATH), "volley.db")


def build_graph(checkpointer=None):
    """
    Assemble and compile the Volley LangGraph agent.

    Phase 6 graph:
        extract_fields → classify → [skip | retrieve_tone] → draft_reply → END

    Phase 7 will extend this with: draft_reply → human_approval → send_email
    """
    g = StateGraph(VolleyState)

    # ── Nodes ──────────────────────────────────────────────────────
    g.add_node("extract_fields", extract_fields)
    g.add_node("classify", classify)
    g.add_node("retrieve_tone", retrieve_tone)
    g.add_node("draft_reply", draft_reply)
    g.add_node("skip", skip)

    # ── Entry point ────────────────────────────────────────────────
    g.set_entry_point("extract_fields")

    # ── Edges ──────────────────────────────────────────────────────
    g.add_edge("extract_fields", "classify")

    g.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "retrieve_tone": "retrieve_tone",
            "skip": "skip",
        },
    )

    g.add_edge("retrieve_tone", "draft_reply")
    g.add_edge("draft_reply", END)
    g.add_edge("skip", END)

    return g.compile(checkpointer=checkpointer)


def get_app():
    """Return a compiled graph with SQLite checkpointing enabled."""
    checkpointer = SqliteSaver.from_conn_string(CHECKPOINT_DB)
    return build_graph(checkpointer=checkpointer)
