from __future__ import annotations

from imgfind.models import Candidate


def print_shortlist(candidates: list[Candidate], verbose: bool = False) -> None:
    if not candidates:
        print("  No candidates found.")
        return

    print()
    for i, c in enumerate(candidates, 1):
        license_marker = ""
        if c.license.is_permissive:
            license_marker = " [FREE]"
        elif c.license.value == "copyrighted":
            license_marker = " [COPYRIGHTED]"

        dims = f"{c.width}x{c.height}" if c.width and c.height else "???"

        scores_parts = []
        if c.relevance_score:
            scores_parts.append(f"rel={c.relevance_score:.2f}")
        if c.aesthetic_score:
            scores_parts.append(f"aes={c.aesthetic_score:.1f}")
        if c.vision_score:
            scores_parts.append(f"vis={c.vision_score:.1f}")
        scores_parts.append(f"score={c.composite_score:.3f}")
        scores_str = " | ".join(scores_parts)

        title = c.title[:60] if c.title else c.url.split("/")[-1][:60]

        print(f"  [{i:2d}] {title}")
        print(f"       {dims} | {c.source}{license_marker} | {scores_str}")
        if verbose and c.vision_rationale:
            print(f"       Vision: {c.vision_rationale}")
        if verbose and c.attribution:
            print(f"       Attribution: {c.attribution}")
        print(f"       {c.url[:100]}")
        print()


def prompt_pick(candidates: list[Candidate]) -> Candidate | None:
    print_shortlist(candidates)
    while True:
        try:
            choice = input("  Pick a candidate (number, or 'q' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if choice.lower() in ("q", "quit", ""):
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]
            print(f"  Enter 1-{len(candidates)}")
        except ValueError:
            print("  Enter a number")
