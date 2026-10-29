# Aircraft maintenance assistant, with real models

The assistant from the series *[Building Reliable AI Over Company Knowledge](https://lesfer.ma/academy/reliable-ai-company-knowledge)*, rebuilt on real components over real documents.

The series builds its assistant for Atlas Bikes, a fictional company, with stand-in models, in the [companion repository](https://github.com/sazangg/lesfer-ma-atlas-bikes-rag). This repository builds it again for **Anfa Aero Services**, a fictional aircraft maintenance shop, over documents that are not fictional: 36 FAA airworthiness directives, four advisory circulars, a type certificate data sheet, four regulations, two handbook chapters, and a 1930 scan. The shop's own documents are fictional and written to fit the real ones: a fleet register, a procedures manual, a training deck, 197 work orders (three of them scanned paper), a logbook extract and an AD compliance record per aircraft, and a price list. 262 documents in all: 49 from the FAA and NACA, 213 from Anfa. See [corpus/README.md](corpus/README.md).

It has one tagged checkpoint per part, like the companion repository, and records at each one what the real system measured. See [CHECKPOINTS.md](CHECKPOINTS.md).

| Part | Article | Tag |
| --- | --- | --- |
| 1 | How an AI assistant answers from company documents | `part-01` |
| 2–14 | | coming |

## Run it without a key

Every model response is recorded in `fixtures/`, so each checkpoint runs offline, free, and gives the same result every time. You need [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env          # ANFA_MODE=replay by default
docker compose up -d --wait   # Postgres with pgvector and BM25
uv run python -m anfa ingest
uv run python -m anfa ask "What must a maintenance record entry contain?"
```

## Run it live

Set `OPENROUTER_API_KEY` in `.env` and `ANFA_MODE=live`. The default models are free on OpenRouter; OpenRouter allows 50 requests a day to them (1,000 once an account has bought 10 credits, which free models don't spend), and ingesting the corpus takes 34. The code calls only models whose name ends in `:free`. Free endpoints may keep what you send: fine for public FAA documents and a fictional company, not for real company documents. With `ANFA_MODE=record`, responses are saved to `fixtures/`.

A changed question, prompt, or model misses its recorded response, so replay mode stops with a message instead of answering something else.

## What's in here

```
corpus/source/faa/    the FAA documents, unchanged (SOURCES.md says where each comes from)
corpus/source/anfa/   the fictional company's documents, built by scripts/build_anfa.py
corpus/parsed/        the parser's output, committed so you don't need Docling installed
scripts/              build_anfa.py and anfa_history.py (the company's documents), parse_sources.py (Docling), excerpt_pdf.py
fixtures/             recorded model responses
anfa/                 the assistant
```

To rebuild the company documents or the parse: `uv run --group corpus python scripts/build_anfa.py` and `uv run --group parse python scripts/parse_sources.py` (Docling downloads its models on first use; the full parse takes about an hour on a CPU).

## License

The code and the Anfa Aero Services documents: MIT, see [LICENSE](LICENSE). The FAA and NACA documents are US government works.
