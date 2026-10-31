"""Command line.

    python -m anfa ingest                       embed the documents and store them (once)
    python -m anfa ask "question" [--show-prompt]
    python -m anfa check [--save-traces]         run the cases against this checkpoint
    python -m anfa ingest-report [--no-corrections]
    python -m anfa measure [--held-out] [--min-score X] [--sweep] [--export-ragas FILE]
    python -m anfa judge-calibration           compare the judge's verdicts with labelled answers
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    measure = commands.add_parser("measure", help="retrieval numbers per question and by kind")
    measure.add_argument("--held-out", action="store_true", help="measure cases/held_out.json instead")
    measure.add_argument("--min-score", type=float, default=0.0, help="drop reranked pieces scoring below this")
    measure.add_argument("--sweep", action="store_true", help="compare minimum scores on both sets")
    measure.add_argument("--export-ragas", metavar="FILE", help="write the questions as a Ragas dataset")
    commands.add_parser("judge-calibration", help="compare the judge's verdicts with labelled answers")
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

    if args.command == "measure":
        from anfa.checks import CASES_FILE
        from anfa.measure import HELD_OUT_FILE, by_kind, export_ragas, mean, measure, stability

        path = HELD_OUT_FILE if args.held_out else CASES_FILE
        if args.export_ragas:
            print(f"Wrote {export_ragas(Assistant(), path, Path(args.export_ragas))} questions.")
            return
        if args.sweep:
            print(f"{'min score':>9}  {'dev recall':>10}  {'dev precision':>13}  {'held-out recall':>15}  {'held-out precision':>18}")
            for floor in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7):
                assistant = Assistant(min_score=floor)
                dev, held = measure(assistant, CASES_FILE), measure(assistant, HELD_OUT_FILE)
                print(f"{floor:>9.1f}  {_f(mean([r.recall for r in dev])):>10}  {_f(mean([r.precision for r in dev])):>13}"
                      f"  {_f(mean([r.recall for r in held])):>15}  {_f(mean([r.precision for r in held])):>18}")
            return
        assistant = Assistant(min_score=args.min_score)
        rows = measure(assistant, path)
        print(f"{'case':<28} {'kind':<20} {'hit':>4} {'recall':>6} {'prec':>5} {'first':>5} {'tokens':>6}  missing")
        for r in rows:
            print(f"{r.case_id:<28} {r.kind:<20} {_f(r.hit):>4} {_f(r.recall):>6} {_f(r.precision):>5} "
                  f"{r.first or '-':>5} {r.tokens:>6}  {'; '.join(r.missing)}")
        print(f"\n{'all':<49} {_f(mean([r.hit for r in rows])):>4} {_f(mean([r.recall for r in rows])):>6} "
              f"{_f(mean([r.precision for r in rows])):>5}")
        print("\nBy kind:")
        for kind, m in by_kind(rows).items():
            print(f"  {kind:<26} {m['questions']:>2} questions  hit {_f(m['hit'])}  recall {_f(m['recall'])}  "
                  f"precision {_f(m['precision'])}")
        if variants := stability(assistant, path):
            print("\nRewordings:")
            for case_id, variant, ok, detail in variants:
                print(f"  {'same' if ok else 'DIFFERS':<8} {case_id:<26} {variant}  ({detail})")

    if args.command == "judge-calibration":
        from anfa.judge import Judge, calibrate

        results = calibrate(Assistant(), Judge())
        for c in results:
            agree = "agrees" if c.judge == c.label else "DISAGREES"
            print(f"  {c.answer_id}  label {c.label:<12} judge {c.judge:<12} {agree:<10} {c.note}")
            if c.judge != c.label:
                print(f"        judge: {' '.join(c.reason.split())[:300]}")
        print(f"\nThe judge agrees with the labels on {sum(c.judge == c.label for c in results)} of {len(results)}.")


def _f(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    main()
