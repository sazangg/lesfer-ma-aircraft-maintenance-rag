# Checkpoints

One per part of the series, on real documents and real models. Each entry records what the system measured, next to what the article showed with stand-in models on Atlas Bikes. Where they differ, the difference is the lesson.

## part-01: Naive RAG

**Article:** [How an AI Assistant Answers From Company Documents](https://lesfer.ma/academy/reliable-ai-company-knowledge/how-an-ai-assistant-answers-from-company-documents)

**Lands in:** the whole pipeline, built for the first time.

```
Preparing (once):  source files -> parser -> plain text -> 1,200-character chunks -> embeddings (passage) -> Postgres + pgvector
Answering:         question -> embedding (query) -> top-5 chunks (access-filtered in SQL) -> prompt -> language model
```

| Component | Here |
| --- | --- |
| Documents | 262: 49 from the FAA and NACA (`corpus/source/faa/`), 213 from the fictional Anfa Aero Services (`corpus/source/anfa/`), 194 of them work orders |
| Parser | Docling 2.142 for PDFs, scans, Word, slides, and workbooks; a direct reader for the eCFR XML. Output in `corpus/parsed/` |
| Chunks | 3,353, at most 1,200 characters, split by size within each heading's text |
| Embeddings | `nvidia/nemotron-3.5-embed-1b:free` on OpenRouter, 1,024 dimensions |
| Index | Postgres 18 + pgvector 0.8 (HNSW, cosine) |
| Language model | `nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter, temperature 0, up to 4,000 tokens |

The article's chunks are 200 characters, which suits its few short documents. Here they would cut a directive's applicability paragraph into four pieces, so this checkpoint uses 1,200.

**What the system measured** (`ANFA_MODE=replay` reproduces these exactly):

| Question | Retrieved | Answer |
| --- | --- | --- |
| What engine does the Cessna 172S have, and what is its rated power? | Three passages from type certificate data sheet 3A12, none from the 172S section, and two from directives | **Wrong.** "Lycoming IO-360-L2A, rated at 160 horsepower at 2,400 RPM", and 180 hp at 2,700 rpm "when modified by Cessna Modification Kit MK172-72-01", citing section XI. Section XI is the 172R. The 172S, in section XII, is rated 180 hp at 2,700 rpm without any kit. |
| What must a maintenance record entry contain? | 14 CFR 43.9 first (0.593), then AC 43-9C and AC 43-9D | **Correct.** The four items of 14 CFR 43.9(a), from the regulation, with the note that the advisory circulars' other items are the owner's responsibility. |
| List all airworthiness directives that apply to the Cessna 172S. | Five passages from five directives | **Incomplete.** Three directives, out of 26 in the corpus that name the 172S, presented as the ones the passages "explicitly" support. It doesn't claim the list is complete, and doesn't say it isn't. |

The article's Part 1 fails on its list question. With real documents, it fails earlier, on a single fact:
- The type certificate data sheet has one section per model, and every model has an engine, a rated power, and a speed limit.
- The chunk that won holds the 172R's values under the bare section number "XI.". The words "Model 172R" are in the section's heading, which never reaches the chunk text.
- The model reads "the Cessna 172S" in the question, finds an engine and a power in a cited source, and answers. Nothing in the pipeline can tell it that the passage is about another model.

Part 4 keeps a chunk's context with it; Part 6 makes sure the evidence applies to what was asked.

The list question fails as the article predicts: five passages can't hold 26 directives. The answer is careful about each item and silent about what's missing: a reader who doesn't know there are 26 takes three as the answer. In an earlier recording on a smaller collection, the same model said the passages "do not establish a comprehensive list". Nothing in the pipeline makes it say that, and Part 2 starts checking.

**What the real documents added** (Part 3 deals with all of it):
- The Federal Register prints several rules on one page, so a directive's PDF begins with the end of the previous rule and ends with the start of the next one, for other aircraft. Their text is indexed as part of the directive.
- Three-column pages break identifiers across lines: AD 2013-11-11's summary reads "AD 200004-01" for AD 2000-04-01. Print-shop lines ("VerDate Mar<15>2010", "TKELLEY on DSK3SPTVN1PROD with RULES") sit in the text.
- The type certificate data sheet's two-column layout, label on the left and value on the right, comes back as "Engine / Fuel Lycoming IO-360-L2A...": the label "Fuel" lands on the engine's line.
- Some section headings are not recognized, so their text is filed under the previous heading: the chunk labelled section III starts with "IV. Model 172D".
- In AC 43.13-1B Table 7-1, a note printed sideways across the columns is read into the cells: the 8-36 row reads "FOLLOWING TORQUE 12-15", "CAUTION DERIVED FROM 7-9", "CADMIUM 20".
- The 1930 NACA scan has an embedded text layer from an old OCR, and the parser uses it: "T t t 1 nnss Io of Europe", "STRUOTURAL", "COMITTEE", "March 15, 1950" for 1930.
- The training deck loses its speaker notes. The scanned work orders lose a work order number and merge the signatures into the text ("Approved for return to service: A.Tazi alaouí"), at a reported OCR confidence of 0.99.

**What real models added:**
- OpenRouter allows 50 requests a day to free models, or 1,000 once the account has bought at least 10 credits, and 20 a minute either way. The embedder sends 100 chunks per request, so ingesting takes 34 requests; spaced to stay under 20 a minute, about 2 minutes.
- The model reasons before it answers, and the reasoning counts against the token limit. At 1,500 tokens, the list answer stopped mid-sentence; this checkpoint allows 4,000.
- The code refuses to call a model whose name doesn't end in `:free`, so a changed setting can't spend an account's credits.
- Embedding fixtures store each vector as base64 float32. Live, record, and replay all use those numbers, so a recorded run and its replay rank passages identically.

**Stop here if** your questions are single facts, each document is about one thing, and a person reads each answer together with its source. The engine question shows how quickly a collection breaks the second condition.
