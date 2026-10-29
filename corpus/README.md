# The corpus

Two layers: real documents published by the FAA, and the documents of a fictional company that uses them.

**Anfa Aero Services** is a fictional maintenance shop in Casablanca. It looks after the Cessna 172 fleet of a fictional flight school, Tadla Flight Academy: seven aircraft registered in Morocco (CN-TFA to CN-TFG). The FAA is the state of design for the Cessna 172, so its airworthiness directives apply to these aircraft, as they do to Cessnas around the world.

## `source/faa/`: real documents

US government works, committed unchanged. [faa/SOURCES.md](source/faa/SOURCES.md) says where each one comes from.

| Folder | Documents | What makes them hard |
| --- | --- | --- |
| `ad/` | 36 airworthiness directives (ADs) for the Cessna 172R and 172S and for equipment installed in them, 1997 to 2020, as printed in the Federal Register | Three-column pages; identifiers broken across lines ("AD 200004-01"); print-shop lines in the text; each PDF also holds the end of the previous rule and the start of the next one, for other aircraft; three files are corrections to an earlier rule; applicability by serial number range, by installed equipment, by part number, and by software version |
| `ac/` | AC 43-9C (cancelled in September 2025) and AC 43-9D (its replacement), on maintenance records; chapter 7 of AC 43.13-1B, on aircraft hardware; AC 43.13-2B, on alterations (137 pages); AC 39-7D, on airworthiness directives | Two revisions of one document, with the sections renumbered; tables with multi-level headers and a rotated note printed across the columns; a long manual of drawings and tables |
| `tcds/` | Type certificate data sheet 3A12, revision 89: every Cessna 172 model from 1955 to today | 33 pages of label-and-value pairs in two columns; one section per model, and the models differ in every value |
| `cfr/` | 14 CFR Parts 39, 43, and 145, and Part 91 subpart E, as eCFR XML | The easy case: the structure is in the file |
| `handbook/` | Two chapters of the FAA's Aviation Maintenance Technician Handbook: records and forms, and mechanic privileges | Say much of what the regulations and advisory circulars say, in other words: passages that compete with the source a question needs |
| `naca/` | NACA Technical Memorandum 579 (1930), a scan | An old scan whose embedded text layer is itself a poor OCR |

## `source/anfa/`: the fictional company

Written for teaching by `scripts/build_anfa.py`. The serial numbers, part numbers, and equipment are chosen to fall inside, outside, and just next to the ranges in the real directives. The work orders, logbooks, and AD compliance records come from one history (`scripts/anfa_history.py`): each aircraft's hours follow straight lines between the figures the documents state, and every inspection, repair, and due date is derived from them. Three records disagree on purpose, as real files do; the script's docstring lists them.

| File | What it is | What makes it realistic |
| --- | --- | --- |
| `fleet-register-2026-10.xlsx` | Aircraft, installed equipment, time-controlled parts | Three sheets; the hours remaining on each part are not in it, only what they are computed from |
| `procedures-manual-r7.docx` | The shop's procedures (excerpt) | Company rules stricter than the directives they follow |
| `training-airworthiness-directives.pptx` | Training deck for new mechanics | The key facts are in the speaker notes |
| `work-orders-scanned.pdf` | Three work orders done on paper, scanned | Page images only; one installation time differs from the fleet register by two swapped digits |
| `work-orders/` | 194 work orders from January 2024 to October 2026, printed from the maintenance system | Many near-identical documents: 153 inspections that differ in a date, a number, and a finding or two |
| `logbooks/` | Each aircraft's logbook entries for the same period, as a printed table | The same events as the work orders, in fewer words: two sources for every answer |
| `ad-records/` | Each aircraft's AD compliance record: every AD in the collection, whether it applies and why, and how it was met | The answer to "which ADs apply" already worked out, with mistakes in it |
| `price-list-2026.xlsx` | Parts and labour prices | Readable by management only |

Document-level metadata (access, document type, AD number, effective date, revision) comes from the document management system, not from the text: see `source/catalog.json`. Access groups: `employees` (everyone), `staff` (mechanics and quality), `management`.

## `parsed/`: what the parser returned

One JSON file per document, written by `scripts/parse_sources.py`: Docling for PDFs, scans, Word, slides, and workbooks; a direct reader for the eCFR XML. Nothing is cleaned up. Each element has a type and, for paged documents, a page number:

```text
heading      text, level
paragraph    text
table        header (or null when the parser marked none), rows
figure       caption, image (in figures/)
slide        slide number, title, text, notes
page_header  text      (repeated page furniture)
page_footer  text
```

Elements from pages the parser had to read as pixels also carry `ocr_confidence`.
