"""Command line.

    python -m anfa ingest                       embed the documents and store them (once)
    python -m anfa ask "question" [--show-prompt]
    python -m anfa check [--save-traces]         run the cases against this checkpoint
    python -m anfa ingest-report [--no-corrections]
"""

from __future__ import annotations

import argparse
import sys

from anfa import CHECKPOINT


def main() -> None:
    parser = argparse.ArgumentParser(prog="anfa", description=f"Anfa assistant ({CHECKPOINT})")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest", help="embed the parsed documents and store them in Postgres")
    ask = commands.add_parser("ask", help="answer one question")
    ask.add_argument("question")
    ask.add_argument("--show-prompt", action="store_true")
    check = commands.add_parser("check", help="run the cases against this checkpoint")
    check.add_argument("--save-traces", action="store_true", help="write each trace to traces/")
    report = commands.add_parser("ingest-report", help="show what conversion changed and what needs review")
    report.add_argument("--no-corrections", action="store_true", help="ignore corpus/corrections.json")
    args = parser.parse_args()

    from anfa.corpus import load_corpus
    from anfa.pipeline import Assistant

    if args.command == "ingest":
        added = Assistant().ingest(load_corpus())
        print(f"Indexed {added} chunks." if added else "The index already holds these chunks; nothing to do.")
        return

    if args.command == "ingest-report":
        assistant = Assistant()
        assistant.convert(load_corpus(), corrections={} if args.no_corrections else None)
        for r in assistant.reports:
            print(f"{r.source_id} ({r.file})")
            for line in r.lines():
                print(f"  - {line}")
        return

    if args.command == "ask":
        trace = Assistant().ask(args.question)
        print(f"[{CHECKPOINT}] {trace.question}\n\nRetrieved:")
        for chunk_id, score in trace.retrieved:
            print(f"  {score:5.3f}  {chunk_id}")
        if args.show_prompt:
            print(f"\nPrompt:\n{trace.prompt}")
        print(f"\nAnswer ({trace.status}):\n{trace.answer}")

    if args.command == "check":
        from anfa.checks import run

        results = run(Assistant(), save_traces=args.save_traces)
        print(f"Checkpoint {CHECKPOINT}\n")
        for r in results:
            print(f"  {r.label:<20} {r.case_id:<26} {r.detail}")
        regressions = sum(r.label == "REGRESSION" for r in results)
        gaps = sum(r.label.startswith("KNOWN GAP") for r in results)
        print(f"\n{len(results) - regressions - gaps} passing, {gaps} known gaps, {regressions} regressions")
        sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
