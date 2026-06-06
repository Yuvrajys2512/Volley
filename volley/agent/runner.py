"""
Runner: orchestrates the graph execution + CLI approval loop for a single email.

Flow:
  1. invoke() → graph runs until human_approval interrupt → pauses
  2. show_approval_prompt() → print draft, ask user [A/E/S]
  3. invoke(Command(resume=...)) → graph resumes → sends or skips
"""

import uuid

from langgraph.types import Command

DIVIDER = "─" * 65
BOLD = "\033[1m"
RESET = "\033[0m"


def process_email(app, email: dict) -> dict:
    """
    Run the full agent loop for one email, including the CLI approval prompt.
    Returns the final graph state.
    """
    thread_id = email.get("id") or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # ── Phase 1: run until interrupt ───────────────────────────────
    state = app.invoke({"email": email}, config=config)

    # If the email was skipped (not a lead), graph ends without interrupting
    if not state.get("is_lead"):
        return state

    # ── Phase 2: show draft and collect decision ───────────────────
    decision = _show_approval_prompt(state)

    # ── Phase 3: resume graph with user's decision ─────────────────
    final_state = app.invoke(Command(resume=decision), config=config)
    return final_state


def _show_approval_prompt(state: dict) -> dict:
    """
    Display the draft in the terminal and collect the user's decision.
    Returns a decision dict to pass to Command(resume=...).
    """
    print(f"\n{DIVIDER}")
    print(f"{BOLD}NEW DRAFT READY FOR REVIEW{RESET}")
    print(DIVIDER)
    print(f"From:    {state.get('sender')}")
    print(f"Subject: {state.get('subject')}")
    print(f"\n{BOLD}Inbound email:{RESET}")
    body_preview = (state.get("body") or "")[:400]
    print(body_preview + ("..." if len(state.get("body", "")) > 400 else ""))
    print(f"\n{BOLD}Draft reply:{RESET}")
    print(DIVIDER)
    print(state.get("draft", ""))
    print(DIVIDER)
    print("\n  [A] Approve and send")
    print("  [E] Edit before sending")
    print("  [D] Save to Gmail Drafts (review and send from Gmail later)")
    print("  [S] Skip (don't send)")
    print()

    while True:
        choice = input("Your choice: ").strip().lower()

        if choice == "a":
            print("Approved. Sending...")
            return {"status": "approved"}

        elif choice == "d":
            print("Saving to Gmail Drafts...")
            return {"status": "drafted"}

        elif choice == "e":
            print("Paste your edited reply below.")
            print("When done, type END on a new line and press Enter:\n")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            edited = "\n".join(lines).strip()
            if not edited:
                print("Empty reply — skipping instead.")
                return {"status": "skipped"}
            print("\nEdited reply saved. Sending...")
            return {"status": "edited", "edited_text": edited}

        elif choice == "s":
            print("Skipped.")
            return {"status": "skipped"}

        else:
            print("Please enter A, E, D, or S.")
