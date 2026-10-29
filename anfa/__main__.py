"""Command line.

    python -m anfa ingest                       embed the documents and store them (once)
    python -m anfa ask "question" [--show-prompt]
"""

from __future__ import annotations

import argparse

from anfa import CHECKPOINT


def main() -> None:
    parser = argparse.ArgumentParser(prog="anfa", description=f"Anfa assistant ({CHECKPOINT})")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest", help="embed the parsed documents and store them in Postgres")
    ask = commands.add_parser("ask", help="answer one question")
    ask.add_argument("question")
    ask.add_argument("--show-prompt", action="store_true")
    args = parser.parse_args()

    from anfa.corpus import load_corpus
    from anfa.pipeline import Assistant

    if args.command == "ingest":
        added = Assistant().ingest(load_corpus())
        print(f"Indexed {added} chunks." if added else "The index already holds these chunks; nothing to do.")
        return

    if args.command == "ask":
        trace = Assistant().ask(args.question)
        print(f"[{CHECKPOINT}] {trace.question}\n\nRetrieved:")
        for chunk_id, score in trace.retrieved:
            print(f"  {score:5.3f}  {chunk_id}")
        if args.show_prompt:
            print(f"\nPrompt:\n{trace.prompt}")
        print(f"\nAnswer ({trace.status}):\n{trace.answer}")


if __name__ == "__main__":
    main()
