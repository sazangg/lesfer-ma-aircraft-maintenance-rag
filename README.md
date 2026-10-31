# Aircraft maintenance assistant, with real models

The assistant from the series *[Building Reliable AI Over Company Knowledge](https://lesfer.ma/academy/reliable-ai-company-knowledge)*, rebuilt on real components over real documents.

The series builds its assistant for Atlas Bikes, a fictional company, with stand-in models, in the [companion repository](https://github.com/sazangg/lesfer-ma-atlas-bikes-rag). This repository builds it again for **Anfa Aero Services**, a fictional aircraft maintenance shop, over documents that are not fictional: 36 FAA airworthiness directives, four advisory circulars, a type certificate data sheet, four regulations, two handbook chapters, and a 1930 scan. The shop's own documents are fictional and written to fit the real ones: a fleet register, a procedures manual, a training deck, 197 work orders (three of them scanned paper), a logbook extract and an AD compliance record per aircraft, and a price list. 262 documents in all: 49 from the FAA and NACA, 213 from Anfa. See [corpus/README.md](corpus/README.md).

It has one tagged checkpoint per part, like the companion repository, and records at each one what the real system measured. See [CHECKPOINTS.md](CHECKPOINTS.md).

| Part | Article | Tag |
| --- | --- | --- |
| 1 | How an AI assistant answers from company documents | `part-01` |
| 2 | When a useful answer isn't a correct answer | `part-02` |
| 3 | From raw files to structured documents | `part-03` |
| 4 | From documents to evidence | `part-04` |
| 5 | When search misses the evidence | `part-05` |
| 6 | Choosing the evidence that applies | `part-06` |
| 7–14 | | coming |

## Run it without a key

Every model response is recorded in `fixtures/`, so each checkpoint runs offline, free, and gives the same result every time. You need [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env          # ANFA_MODE=replay by default
docker compose up -d --wait   # Postgres with pgvector and BM25
uv run python -m anfa ingest
uv run python -m anfa ask "What must a maintenance record entry contain?"
```

## Check a checkpoint

```bash
uv run python -m anfa check                 # add --save-traces to write each trace to traces/
```

Each case in `cases/cases.json` states the part meant to handle it. Failing cases that a later part will close are reported as known gaps, not errors; a failure the current checkpoint should handle is a regression.

## Run it live

Set `OPENROUTER_API_KEY` in `.env` and `ANFA_MODE=live`. The default models are free on OpenRouter; OpenRouter allows 50 requests a day to them (1,000 once an account has bought 10 credits, which free models don't spend), and ingesting the corpus takes about 218: 171 to describe the figures, 47 to embed the searched pieces. Each question then takes three: one to embed it, one to rerank the candidates, one to answer. The code calls only models whose name ends in `:free`. Free endpoints may keep what you send: fine for public FAA documents and a fictional company, not for real company documents. With `ANFA_MODE=record`, recorded responses are replayed and only the missing ones are requested and saved to `fixtures/`.

A changed question, prompt, or model misses its recorded response, so replay mode stops with a message instead of answering something else.

## See what preparing the documents changed

```bash
uv run python -m anfa ingest-report                    # per document: what was removed, repaired, restored, corrected, and what needs a person
uv run python -m anfa ingest-report --no-corrections   # the same, ignoring the reviewed corrections in corpus/corrections.json
uv run pytest -q                                       # the converter's tests; no model is called
```

## What's in here

```
corpus/source/faa/    the FAA documents, unchanged (SOURCES.md says where each comes from)
corpus/source/anfa/   the fictional company's documents, built by scripts/build_anfa.py
cases/                cases.json: regression cases, one or two per part; eval.json: about 100 questions for measuring
corpus/parsed/        the parser's output, committed so you don't need Docling installed
corpus/corrections.json  corrections a person made after checking a page, each tied to the parse it was written against
scripts/              build_anfa.py and anfa_history.py (the company's documents), build_eval.py, parse_sources.py (Docling), excerpt_pdf.py
fixtures/             recorded model responses
anfa/                 the assistant
tests/                tests that need no model (the converter, the evidence units)
```

To rebuild the company documents or the parse: `uv run --group corpus python scripts/build_anfa.py` and `uv run --group parse python scripts/parse_sources.py` (Docling downloads its models on first use; the full parse takes about an hour on a CPU). `uv run python scripts/build_eval.py` rebuilds `cases/eval.json` from the same history the company's records are written from.

## License

The code and the Anfa Aero Services documents: MIT, see [LICENSE](LICENSE). The FAA and NACA documents are US government works.
