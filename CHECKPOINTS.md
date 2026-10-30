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
- The 1930 NACA scan comes back garbled: "T t t 1 nnss Io of Europe", "STRUOTURAL", "COMITTEE", "March 15, 1950" for 1930. (This note first blamed the scan's embedded text layer. Part 3 found the opposite: the text layer is good, and the garble came from the parser's own OCR.)
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

## part-03: From raw files to structured documents

**Article:** [From Raw Files to Structured Documents](https://lesfer.ma/academy/reliable-ai-company-knowledge/from-raw-files-to-structured-documents)

**Lands in:** ingestion. Answering doesn't change.

```
Preparing (once):  parser output -> conversion (anfa/convert.py) -> structured documents + ingestion report
                   -> rendered text -> 1,200-character chunks -> embeddings -> Postgres + pgvector
```

`anfa/convert.py` turns each parsed document into the document a reader would recognize, and reports what it did. `python -m anfa ingest-report` prints the report; `--no-corrections` shows the documents without the reviewed corrections.

| Step | On these documents |
| --- | --- |
| Drop page furniture | Running headers and footers, and the Federal Register's print-shop lines ("VerDate", "BILLING CODE", "TKELLEY on DSK3SPTVN1PROD with RULES", bare page numbers) |
| Keep only the directive | A rule starts at "DEPARTMENT OF TRANSPORTATION" above the docket line that names the directive, and ends at its own "[FR Doc." line. In 35 of the 36 directives, between 6 and 83 elements of other rules go |
| Apply reviewed corrections | `corpus/corrections.json`: Table 7-1 rebuilt from the page, and six lines of the scanned work orders. Each is tied to a fingerprint of the element it was written against; if a new parse changes that element, the correction isn't applied and the report asks for another look |
| Repair predictable breaks | 10 AD numbers split at a line break ("AD 200324-13"); misprints quoted by correction notices, and EASA's own numbering (AD 2007-0232), left alone. TCDS section IV promoted from paragraph to heading |
| Rejoin tables | Tables split across pages (43 parts in AC 43.13-1B chapter 7, one or two per logbook); the "TABLE 7-1." caption attached to its table; each workbook table scoped by its sheet name, which the parser drops |
| Put back what the parser left out | The training deck's speaker notes, read from the PPTX |
| Describe figures | 171 figures, by `nvidia/nemotron-3.5-super-vl:free` |
| Report what needs a person | Pages whose text came from OCR and that nobody has checked against the image |

**What the runner measured:**

```
PASS                 C01-record-entry           all 1 supplied; 'A description (...) of work performed' supplied
PASS                 C02-price-access           none supplied
PASS                 C03-torque-row             '8-36 12-15 7-9 20 12' supplied
PASS                 C04-slide-notes            'applied once' supplied
PASS                 C05-scanned-signature      'Approved for return to service: A. Tazi' supplied
KNOWN GAP -> part-04 C06-engine-model-context   ['172S', 'Rated 180 Horsepower'] not in the same passage
KNOWN GAP -> part-05 C07-exact-ad-number        first is AD-2013-11-11
EARLY PASS           C08-part-number            all 1 supplied
KNOWN GAP -> part-06 C09-engine-only-172S       'IO-360-L2A, Rated' not supplied
KNOWN GAP -> part-06 C10-which-aircraft         status answered
KNOWN GAP -> part-09 C11-every-ad               missing 17 of 21; completeness not guaranteed
KNOWN GAP -> part-10 C12-switch-hours           answer lacks ['39.4']
KNOWN GAP -> part-11 C13-muffler-fleet          answer lacks ['CN-TFA', 'CN-TFF']
KNOWN GAP -> part-12 C14-records-trail          missing 1 of 3: ['AD-2013-11-11']
KNOWN GAP -> part-13 C15-revision-diff          all 2 supplied; 'Overview of FAA Form 8130-3' not supplied

6 passing, 9 known gaps, 0 regressions
```

The index holds 3,091 chunks, down from 3,353: the neighbouring rules and the print-shop lines are gone.

**What the real documents added:**
- **The OCR's confidence can't sort pages for review.** Docling scored every page of the scanned work orders 0.99, including the lines where it read a handwritten signature as text ("Approved for return to service: A.Tazi alaouí"). The article flags text below a confidence threshold; here nothing would be flagged. So the converter lists a scanned page as needing review until a person has checked it against the image (`reviewed_pages` in `corpus/corrections.json`).
- **An OCR score on a page doesn't mean its text came from OCR.** The parser runs OCR on every bitmap, so printed advisory circulars get scores because of their figures. A page counts as OCR'd when the parser found much more text on it than the PDF's own text layer holds. That leaves three pages of printed documents to check, plus the NACA scan.
- **The NACA scan's text layer is better than a new OCR.** Part 1 blamed the text layer for the garble. The layer reads "The success of the 1929 International Light Airplane Tour"; the parser's OCR read "T t t 1 nnss Io of Europe". Forcing full-page OCR made no difference. The catalog now tells the parser to skip OCR on that scan (`"parse": {"ocr": "off"}`), and the converter still lists all 31 pages as unchecked: the layer came from an earlier OCR and has its own slips ("COITTEE").
- **Columns interleave.** Where two rules share a page, the parser sometimes reads their columns alternately. AD 2001-06-17's correction notice keeps a few lines of the Cessna 750 rule printed beside it: the reading order gives no way to separate them.
- **Some tables need a person.** Table 7-1's sideways caution went into the cells of its first row and its bottom note into its last, and the two-level header came back in fragments. No rule recovers that; the reviewed correction does.

**What real models added:**
- The vision model reasons by default. On AC 43.13-1B Figure 7-27 it spent all 4,000 tokens reasoning and returned no description, five times in a row. With reasoning off, a figure takes about 5 seconds and the description is complete. Ingesting now takes 171 requests for figures and 31 for embeddings.
- Fixtures store an image as its hash, not its bytes: the image is in `corpus/figures/`.
- **The index stopped finding the evidence for one question.** pgvector's HNSW index keeps 40 candidates by default. After conversion, the 194 work orders' header chunks are nearly identical, and for "Is CN-TFE's oil pressure switch within the limit of AD 2013-11-11?" the search returned five of those headers (similarity 0.31) instead of the fleet register's switch row (0.62). An exact search found it. At `hnsw.ef_search = 100`, all 15 cases match an exact search. An approximate index is a setting to measure, not a default to trust.

**The engine question changed answer.** Retrieval still misses the 172S section (Part 4's job), but the model now says the passages "do not establish the engine and rated power for the Cessna 172S", where Part 1 answered with the 172R's values. Nothing in this checkpoint asks for that: the passages changed, and the model behaved differently. One more reason the checks look at evidence, not wording.

**Stop here if** your documents are born digital or a person checks the scanned ones, and each question is answered by one passage. The next gaps are about how text is cut and found, not about the text itself.

## part-04: From documents to evidence

**Article:** [From Documents to Evidence](https://lesfer.ma/academy/reliable-ai-company-knowledge/from-documents-to-evidence)

**Lands in:** ingestion, plus one answering step.

What is easy to find is often not what the model needs to read. Each kind of content now gets a **searched form** and a **supplied form** (`anfa/evidence.py`):

| Kind | Searched as | Supplied to the model as |
| --- | --- | --- |
| paragraphs | up to 1,200 characters of a section's text | the whole section |
| table | a table of up to 12 rows whole; a longer one row by row, each cell labelled with its column ("Work order: WO-2024-0284") | the whole table, with its caption, header, and note |
| figure | caption and description | caption, description, image file, page |
| slide | title, text, speaker notes | the whole slide |

Every searched piece starts with the document's title and its section heading. The article searches paragraphs alone, under their section title. Here that isn't enough: a work order's "Replaced engine oil pressure switch" paragraph never names the aircraft; its title does.

A block is at most about 6,000 characters. A longer section or table is supplied in consecutive parts, each with its heading, and each table part with its header. The article's documents are short enough to supply whole; a 150-row logbook isn't.

```
Preparing:  structured documents -> searchable pieces (embedded, 4,633) + blocks (stored, 2,535)
Answering:  question -> top-5 pieces -> the block each belongs to, once -> prompt
```

**What the runner measured:**

```
PASS                 C01-record-entry           all 1 supplied; 'A description (...) of work performed' supplied
PASS                 C02-price-access           none supplied
PASS                 C03-torque-row             '8-36 12-15 7-9 20 12' supplied
PASS                 C04-slide-notes            'applied once' supplied
PASS                 C05-scanned-signature      'Approved for return to service: A. Tazi' supplied
PASS                 C06-engine-model-context   ['172S', 'Rated 180 Horsepower'] together in one passage
EARLY PASS           C07-exact-ad-number        first is AD-2000-04-01
EARLY PASS           C08-part-number            all 1 supplied
EARLY PASS           C09-engine-only-172S       every passage with 'IO-360-L2A, Rated' names '172S'
KNOWN GAP -> part-06 C10-which-aircraft         status answered
KNOWN GAP -> part-09 C11-every-ad               missing 19 of 21; completeness not guaranteed
KNOWN GAP -> part-10 C12-switch-hours           answer lacks ['39.4']
KNOWN GAP -> part-11 C13-muffler-fleet          answer lacks ['CN-TFA', 'CN-TFF']
KNOWN GAP -> part-12 C14-records-trail          missing 3 of 3: ['FLEET-2026-10', 'WO-SCAN', 'AD-2013-11-11']
KNOWN GAP -> part-13 C15-revision-diff          all 2 supplied; 'Overview of FAA Form 8130-3' not supplied

9 passing, 6 known gaps, 0 regressions
```

**Closed gap:** the engine question. The model receives section XII of the type certificate data sheet whole, with "Model 172S, Skyhawk SP" above "Engine Lycoming IO-360-L2A, Rated 180 Horsepower", and answers "Lycoming IO-360-L2A, rated at 180 horsepower", citing section XII. Part 1 gave the 172R's values; Part 3 said the passages didn't establish it.

**Early passes:**
- **C09** (Part 6's case): every passage that gives an engine and a power now names its model, because the section's heading travels with it. Part 6 still has its own job: making sure an answer uses only the evidence for the aircraft asked about.
- **C07** (Part 5's case): asked "What does AD 2000-04-01 require?", that directive now ranks first. Each of its pieces starts with its title, "AD 2000-04-01: ...", so the number is in the searched text of every piece, not only where the body mentions it. Vector search still has no notion of an exact code; Part 5 adds one.

**What the real documents added:**
- **One file can hold several documents.** The scanned file holds three work orders, and its title names none of their aircraft. With the title prefix, the CN-TFE switch question (C05) found CN-TFD's work order instead, a regression. The person who checks a scan against its image now also records what each page is (`page_titles` in `corpus/corrections.json`), and each page's sections carry that title.
- **9 of 170 figure descriptions were loops, not descriptions.** The vision model, with reasoning off, sometimes repeats a pattern until it runs out of tokens ("80-3/4 IN. CABLE, 81 IN. CABLE, 81-1/4 IN. CABLE, ..."). Part 3 indexed them. A description that reaches the token limit is now treated as no description: the figure is searched by its caption, and the ingestion report lists it for a person.
- **The records disagree, and the model blends them.** Asked how many hours CN-TFE's switch has left (C12), the model now receives both the fleet register (installed at 10,560.2 hours) and the AD compliance record (10,650.2). It quotes the first as the installation time and the second's due point as if they agreed, and says, correctly, that it lacks the current hours. It never notices that the two records conflict. Parts 11 and 12 deal with records that disagree.
- **Same evidence, opposite conclusions.** Asked whether that switch is within its limit (C14), the model answers "Yes", from the compliance record's next due point, without the current hours it said in C12 that it needed.

**What real models and infrastructure added:**
- **The approximate index was not reproducible.** Part 3 raised HNSW's `ef_search` to 100 after the default missed one case's evidence. With 4,633 pieces, it missed again: for C02, a fresh build of the index returned a piece at similarity 0.546 that the recorded run never saw, and its best was 0.44. Which pieces an HNSW index misses depends on how the graph was built, so a recorded run and a replay can retrieve different passages. This checkpoint drops the index and compares the question with every piece: exact, identical on every build, and a few milliseconds at this size. An approximate index pays off at hundreds of thousands of vectors, not a few thousand.
- Ingesting now takes 47 embedding requests (4,633 pieces, 100 per request), plus the 171 figure descriptions.

**Stop here if** each question is answered by one passage, table, figure, or slide, and plain wording is enough to find it. C07 passing here is luck of the title prefix; Part 5 makes exact codes reliable.
