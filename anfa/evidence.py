"""Part 4: from structured documents to evidence.

What is easy to find is often not what the model needs to read. So every piece of content gets
two forms:

    kind        searched as                                     supplied to the model as
    ---------   ---------------------------------------------   -----------------------------------
    paragraphs  up to 1,200 characters of a section's text      the whole section
    table       a small table whole; a large one row by row,    the whole table, caption, header,
                each cell labelled with its column              and note included
    figure      caption + description                           caption, description, image file, page
    slide       title, text, speaker notes                      the whole slide

Every searched piece starts with the document's title and its section heading. A paragraph of a
work order ("Replaced engine oil pressure switch...") doesn't name the aircraft; the title does.

Search returns small pieces. Each piece points to the block it belongs to (`parent_id`), and the
model receives that block. A block is at most 6,000 characters: a section or table longer than
that is supplied in consecutive parts, each with its heading, and a table part with its header.

Part 6: a piece also records what it applies to, when that is narrower than its document, so a
search can leave out what doesn't apply (anfa/situation.py):

    models    a section headed "Model 172S, Skyhawk SP" or "Models 172D, 172E, ..." (type certificate)
    aircraft  a table row with a Registration column; a page a reviewer recorded (`page_meta`)
"""

from __future__ import annotations

import re

from anfa.chunking import Chunk, _pieces
from anfa.convert import Element, StructuredDocument

SEARCH_CHARS = 1200
BLOCK_CHARS = 6000
# A table with more rows than this is searched row by row: a whole logbook in one vector finds nothing.
WHOLE_TABLE_ROWS = 12
# A heading that names the models its section is about. "Models 172 thru 172Q" names a range: untagged.
MODELS_HEADING = re.compile(r"^(?:Data Pertinent to )?Models? 172")
MODEL = re.compile(r"\b172[A-Z]?\b")


def evidence_units(doc: StructuredDocument) -> tuple[list[Chunk], list[Chunk]]:
    """Return (searchable pieces, blocks supplied to the model)."""
    searchable: list[Chunk] = []
    blocks: list[Chunk] = []
    title = doc.meta.get("title", doc.source_id)

    for s, section in enumerate(doc.sections):
        heading = f"{section.number} {section.title}".strip()
        context = "\n".join(x for x in (title, section.context, heading) if x)
        prefix = f"{doc.source_id}-s{s}"
        meta = {**doc.meta, **section.meta}
        if MODELS_HEADING.match(section.title) and " thru " not in section.title:
            meta["models"] = MODEL.findall(section.title)

        def block(suffix: str, body: str, kind: str) -> Chunk:
            b = Chunk(f"{prefix}{suffix}", f"{context}\n\n{body}", doc.source_id, section.number,
                      {**meta, "element": kind})
            blocks.append(b)
            return b

        def piece(parent: Chunk, n: int, text: str, search: str, row: dict | None = None) -> None:
            searchable.append(Chunk(f"{parent.id}-{n}", text, doc.source_id, section.number, {**meta, **(row or {})},
                                    parent_id=parent.id, search_text=f"{context}\n{search}"))

        # Paragraphs: the section is supplied whole, or in parts that each fit a block.
        prose = [e.render() for e in section.elements if e.kind == "paragraph"]
        for p, part in enumerate(_pack(prose, BLOCK_CHARS)):
            parent = block(f"-text{p}", "\n\n".join(part), "section")
            for n, text in enumerate(_pack([x for t in part for x in _pieces(t, SEARCH_CHARS)], SEARCH_CHARS)):
                piece(parent, n, "\n".join(text), "\n".join(text))

        others = [e for e in section.elements if e.kind != "paragraph"]
        for n, element in enumerate(others):
            d = element.data
            if element.kind == "table":
                _table(element, f"-table{n}", block, piece)
            elif element.kind == "figure":
                body = "\n".join(x for x in (d["caption"], f"Figure description: {d['description']}") if x)
                parent = block(f"-figure{n}", f"{body}\nImage: {d['image']} (page {element.page})", "figure")
                piece(parent, 0, d["caption"] or body[:200], body)
            elif element.kind == "slide":
                parent = block(f"-slide{n}", f"Slide {d['slide']}: {element.render()}", "slide")
                piece(parent, 0, d["title"], element.render())
    return searchable, blocks


def _table(element: Element, suffix: str, block, piece) -> None:
    d = element.data
    head = Element("table", element.page, {**d, "rows": []}).render()  # caption and header, no rows
    rows = ["| " + " | ".join(r) + " |" for r in d["rows"]]
    note = d.get("note", "")
    parts = _pack(rows, BLOCK_CHARS - len(head) - len(note))
    for p, part in enumerate(parts):
        body = "\n".join(x for x in (head, *part, note if p == len(parts) - 1 else "") if x)
        parent = block(f"{suffix}-{p}", body, "table")
        if len(d["rows"]) <= WHOLE_TABLE_ROWS:
            piece(parent, 0, body, body)
            continue
        first = sum(len(x) for x in parts[:p])
        for n, row in enumerate(d["rows"][first:first + len(part)]):
            cells = list(zip(d["header"] or [], row))
            labelled = "; ".join(f"{h}: {c}" for h, c in cells if c) or " ".join(row)
            registration = next((c for h, c in cells if h == "Registration" and c), None)
            applies = {"aircraft": registration} if registration else None
            piece(parent, n, "| " + " | ".join(row) + " |", "\n".join(x for x in (d.get("scope"), labelled) if x), applies)


def _pack(texts: list[str], limit: int) -> list[list[str]]:
    """Consecutive texts, grouped so each group's total length stays within the limit."""
    groups: list[list[str]] = []
    size = 0
    for text in texts:
        if groups and size + len(text) <= limit:
            groups[-1].append(text)
            size += len(text) + 2
        else:
            groups.append([text])
            size = len(text)
    return groups
