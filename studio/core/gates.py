"""Human approval gates.

At a gate the pipeline opens a review page in your browser and asks in the
terminal:  [y] approve   [n] request changes (with notes)   [l] decide later.
Decisions are saved in the manifest; an approval stays valid until the
reviewed content changes.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path
from typing import Callable

from .errors import GatePending, GateRejected
from .manifest import Manifest


def approval_gate(
    manifest: Manifest,
    gate_id: str,
    title: str,
    review_file: Path,
    content_hash: str,
    *,
    open_browser: bool = True,
    input_fn: Callable[[str], str] = input,
    interactive: bool | None = None,
) -> str:
    """Return notes ('' if none) once approved; raise GatePending / GateRejected otherwise."""
    previous = manifest.gate(gate_id)
    if previous.get("decision") == "approved" and previous.get("content_hash") == content_hash:
        return previous.get("notes", "")

    if interactive is None:
        interactive = sys.stdin.isatty()

    print(f"\n🛑  APPROVAL NEEDED — {title}")
    print(f"    Review this file: {review_file}")
    if open_browser:
        try:
            webbrowser.open(Path(review_file).resolve().as_uri())
        except Exception:  # noqa: BLE001 - opening a browser is a convenience only
            pass

    if not interactive:
        manifest.set_gate(gate_id, "pending", content_hash)
        raise GatePending(
            f"{title} is waiting for your approval.",
            fix="Run the same command in a terminal and answer the question.",
        )

    while True:
        answer = input_fn("    Approve? [y] yes  [n] request changes  [l] later: ").strip().lower()
        if answer in ("y", "yes"):
            notes = input_fn("    Optional notes (Enter to skip): ").strip()
            manifest.set_gate(gate_id, "approved", content_hash, notes)
            print("    ✅ Approved.")
            return notes
        if answer in ("n", "no"):
            notes = input_fn("    What should change? ").strip()
            manifest.set_gate(gate_id, "changes_requested", content_hash, notes)
            raise GateRejected(
                f"{title}: changes requested.",
                fix="Your notes are saved. Re-run the same command: this stage will be "
                "regenerated using your notes.",
            )
        if answer in ("l", "later"):
            manifest.set_gate(gate_id, "pending", content_hash)
            raise GatePending(f"{title} is waiting for your approval.",
                              fix="Re-run the same command when you're ready to decide.")
        print("    Please type y, n or l.")
