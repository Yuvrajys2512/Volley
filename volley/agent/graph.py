from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from volley.agent.state import VolleyState
from volley.agent.nodes import (
    extract_fields, classify, retrieve_tone,
    draft_reply, human_approval, send_email_node, skip,
)
from volley.agent.routing import route_after_classify, route_after_approval
from volley.config import CHROMA_DB_PATH

import os

CHECKPOINT_DB = os.path.join(os.path.dirname(CHROMA_DB_PATH), "volley.db")


def build_graph(checkpointer=None):
    """
    Assemble and compile the Volley LangGraph agent.

    Full graph (Phase 7):
        extract_fields → classify → retrieve_tone → draft_reply
                                  ↘ skip → END     → human_approval → send_email → END
                                                                     ↘ END (skipped)
    """
    g = StateGraph(VolleyState)

    # ── Nodes ──────────────────────────────────────────────────────
    g.add_node("extract_fields", extract_fields)
    g.add_node("classify", classify)
    g.add_node("retrieve_tone", retrieve_tone)
    g.add_node("draft_reply", draft_reply)
    g.add_node("human_approval", human_approval)
    g.add_node("send_email", send_email_node)
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
    g.add_edge("draft_reply", "human_approval")

    g.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "send_email": "send_email",
            "__end__": END,
        },
    )

    g.add_edge("send_email", END)
    g.add_edge("skip", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["human_approval"])


def get_app():
    """Return a compiled graph with SQLite checkpointing enabled."""
    import sqlite3

    # In current LangGraph, SqliteSaver wraps a live sqlite3 connection.
    # from_conn_string() is a context manager, so we build the connection
    # ourselves and keep it open for the life of the process.
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer=checkpointer)
