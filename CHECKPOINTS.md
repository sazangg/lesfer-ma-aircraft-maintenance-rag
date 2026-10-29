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

## part-02: Known questions and a check runner

**Article:** [When a Useful Answer Isn't a Correct Answer](https://lesfer.ma/academy/reliable-ai-company-knowledge/when-a-useful-answer-isnt-a-correct-answer)

**Lands in:** around the pipeline. The pipeline itself doesn't change.

- `cases/cases.json` records 15 questions a mechanic at Anfa asks, with the behavior a correct system shows and the part meant to handle each one. Each expectation was checked against the documents: the 26 directives that name the 172S, the 5 of them that later directives in the collection supersede, the serial ranges, the hours.
- `python -m anfa check` runs them and labels each result PASS, KNOWN GAP, EARLY PASS, or REGRESSION. It exits with an error on a regression, so CI runs it.
- `--save-traces` writes the question, retrieved chunks, prompt, and answer for each case to `traces/`.
- `cases/eval.json` holds 98 more questions for measuring, from Part 7 on: applicability, records, calculations, lists, regulations, identifiers, access, questions the documents can't answer, records that disagree, and superseded documents. 60 are for tuning and 38 are held out. `scripts/build_eval.py` computes every fleet answer from the same history the company's records are written from, so no answer is typed by hand. The 15 cases find a gap; the 98 questions measure how often it shows.

Most checks look at the evidence that reached the model, not at the answer's wording. Text is compared ignoring case, spacing, and most punctuation, so a check still holds when Part 3 renders a table differently.

**What the runner measured:**

```
PASS                 C01-record-entry           all 1 supplied; 'A description (...) of work performed' supplied
PASS                 C02-price-access           none supplied
KNOWN GAP -> part-03 C03-torque-row             '8-36 12-15 7-9 20 12' not supplied
KNOWN GAP -> part-03 C04-slide-notes            'applied once' not supplied
KNOWN GAP -> part-03 C05-scanned-signature      'Approved for return to service: A. Tazi' not supplied
KNOWN GAP -> part-04 C06-engine-model-context   ['172S', 'Rated 180 Horsepower'] not in the same passage
KNOWN GAP -> part-05 C07-exact-ad-number        first is AD-2013-11-11
EARLY PASS           C08-part-number            all 1 supplied
KNOWN GAP -> part-06 C09-engine-only-172S       a passage with 'IO-360-L2A, Rated' doesn't name '172S'
KNOWN GAP -> part-06 C10-which-aircraft         status answered
KNOWN GAP -> part-09 C11-every-ad               missing 17 of 21; completeness not guaranteed
KNOWN GAP -> part-10 C12-switch-hours           answer lacks ['39.4']
KNOWN GAP -> part-11 C13-muffler-fleet          answer lacks ['CN-TFA', 'CN-TFF']
KNOWN GAP -> part-12 C14-records-trail          missing 1 of 3: ['AD-2013-11-11']
KNOWN GAP -> part-13 C15-revision-diff          missing 1 of 2: ['AC-43-9C']; 'Overview of FAA Form 8130-3' not supplied

3 passing, 12 known gaps, 0 regressions
```

**What the traces show:**
- **C10** is the article's lesson on real documents. "Does the oil pressure switch AD apply to our 172S?" retrieves AD 2000-04-01, the directive that AD 2013-11-11 superseded in 2013. The answer gives that old directive's serial numbers with a confident citation. It doesn't ask which aircraft, and it doesn't know the directive is superseded. Useful-looking, and wrong.
- **C07:** asked about AD 2000-04-01 by number, search ranks AD 2013-11-11 first, because the newer directive quotes the older one's number.
- **C08** passes early: vector search found part number 2013142-18. The article says vector search can't see exact codes. That's not a rule. The code is rare and its directive's text repeats it, so here the search found it. C07 shows the same kind of search failing on an AD number.
- **C12** and **C14:** the fleet register's sheets are parsed as separate tables, so the aircraft's current hours and the part's installation hours land in different chunks. The model sees the installation hours and says, correctly, that it can't compute without the current hours. An honest "I can't", and still not an answer.
- **C04:** the model reaches roughly the right answer, that the 50-hour allowance belonged to 2013, from the directive's own paragraph (g)(6). The speaker notes, which say it plainly, never arrive. The check fails on evidence while the answer is useful. That's the point of checking evidence: this time the model reasoned well, next time it may not.
- **C02:** the price list never reaches a mechanic's question, because the access filter runs inside the search query. The model says the passages hold no price.
- **C13:** asked which aircraft AD 2018-02-04 affects, search returns five other directives' applicability paragraphs and not that one. The model says, correctly, that the passages don't mention AD 2018-02-04. Like C07, an exact number that vector search treats as one more similar-looking code.
- **The work orders compete.** Questions about CN-TFE's oil pressure switch (C05, C12, C14) retrieve WO-2025-0095, which replaced CN-TFD's switch: same part, same directive, same wording, wrong aircraft. With 194 work orders that differ in a date, a registration, and a finding, similar text is the normal case.

**Not a stopping point.** Keep this case file and runner whatever you build next. Every later checkpoint is judged by it.