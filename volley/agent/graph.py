import os

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from volley.agent.nodes import (
    classify,
    create_draft_node,
    draft_reply,
    extract_fields,
    human_approval,
    retrieve_tone,
    send_email_node,
    skip,
)
from volley.agent.routing import route_after_approval, route_after_classify
from volley.agent.state import VolleyState
from volley.config import CHROMA_DB_PATH

CHECKPOINT_DB = os.path.join(os.path.dirname(CHROMA_DB_PATH), "volley.db")


def build_graph(checkpointer=None):
    """
    Assemble and compile the Volley LangGraph agent.

    Full graph:
        extract_fields → classify → retrieve_tone → draft_reply → human_approval
                                  ↘ skip → END                  ├ approved/edited → send_email → END
                                                                ├ drafted        → create_draft → END
                                                                ↘ skipped        → END
    """
    g = StateGraph(VolleyState)

    # ── Nodes ──────────────────────────────────────────────────────
    g.add_node("extract_fields", extract_fields)
    g.add_node("classify", classify)
    g.add_node("retrieve_tone", retrieve_tone)
    g.add_node("draft_reply", draft_reply)
    g.add_node("human_approval", human_approval)
    g.add_node("send_email", send_email_node)
    g.add_node("create_draft", create_draft_node)
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
            "create_draft": "create_draft",
            "__end__": END,
        },
    )

    g.add_edge("send_email", END)
    g.add_edge("create_draft", END)
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


def build_server_graph(gmail_service=None, repo=None):
    """
    Assemble and compile the drafts-only server graph used by the multi-tenant
    worker: no human_approval interrupt, no send_email path (no gmail.send
    scope on the server — every reply lands in Gmail Drafts for the user to
    review and send themselves).

    Server graph:
        extract_fields → classify → retrieve_tone → draft_reply → create_draft → END
                                  ↘ skip → END

    Compiled with checkpointer=None: a run either completes in one shot or is
    retried by the worker's own job/dedup bookkeeping — LangGraph's own
    checkpoint/resume machinery isn't needed here.

    `gmail_service`/`repo` (the per-user Gmail client and DB-repo for this
    invocation — neither reliably serializable) are bound via closures at
    build time rather than threaded through as graph state or LangGraph's
    `config["configurable"]`: passing custom objects through node `config`
    was observed to be unreliable across steps (LangGraph rebuilds/filters
    the config it hands to each node), whereas a plain Python closure is
    simple and deterministic. The worker builds one graph per message (or
    reuses one per account, since these are set once per invoke call).
    """

    def _retrieve_tone(state):
        return retrieve_tone(state, config={"configurable": {"repo": repo}})

    def _create_draft(state):
        return create_draft_node(
            state, config={"configurable": {"gmail_service": gmail_service, "repo": repo}}
        )

    g = StateGraph(VolleyState)

    g.add_node("extract_fields", extract_fields)
    g.add_node("classify", classify)
    g.add_node("retrieve_tone", _retrieve_tone)
    g.add_node("draft_reply", draft_reply)
    g.add_node("create_draft", _create_draft)
    g.add_node("skip", skip)

    g.set_entry_point("extract_fields")
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
    g.add_edge("draft_reply", "create_draft")
    g.add_edge("create_draft", END)
    g.add_edge("skip", END)

    return g.compile(checkpointer=None)
