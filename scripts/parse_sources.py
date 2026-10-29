"""Parse the source documents and write the result as parser output, one JSON file per document.

PDFs (printed, scanned), Word, slides, and Excel go through Docling. The two regulations are the
eCFR's XML, which already says what is a heading, a paragraph, and a table, so they are read
directly: a layout model has nothing to find there.

The output lands in corpus/parsed/ and is committed: readers don't need Docling installed, and
the parse is part of what each checkpoint can be compared on. See corpus/README.md for the
element format.

Nothing is cleaned up here. Page headers and footers, the Federal Register's print-shop lines,
the neighbouring rules printed on the same pages, a table broken by a rotated note, a scan's OCR
mistakes, and what the parser leaves out all pass through as the parser reported them.

    uv run --group parse python scripts/parse_sources.py            every document
    uv run --group parse python scripts/parse_sources.py PROC-R7    only these
"""

from __future__ import annotations

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "corpus" / "source"
OUT = ROOT / "corpus" / "parsed"
FIGURES = ROOT / "corpus" / "figures"
FORMATS = {".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx", ".xml": "xml"}


# --- Docling ------------------------------------------------------------------------------------

def converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.generate_picture_images = True  # keep each figure as an image, next to its caption
    options.images_scale = 2.0
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


def table_element(item) -> dict:
    grid = [[cell.text for cell in row] for row in item.data.grid]
    header_flags = [any(c.column_header for c in row) for row in item.data.grid]
    header = grid[0] if grid and header_flags[0] else None
    return {"type": "table", "header": header, "rows": grid[1:] if header else grid}


def docling_elements(doc, source_id: str, is_slides: bool) -> list[dict]:
    from docling_core.types.doc import ContentLayer, DocItemLabel, PictureItem, TableItem

    layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    picture_captions = {ref.cref for p in doc.pictures for ref in p.captions}
    elements: list[dict] = []
    slides: dict[int, dict] = {}
    figure_no = 0
    for item, _level in doc.iterate_items(included_content_layers=layers):
        page = item.prov[0].page_no if getattr(item, "prov", None) else None
        if is_slides:  # one element per slide: its title and its text, as the parser reported them
            slide = slides.setdefault(page, {"type": "slide", "slide": page, "title": "", "text": "", "notes": ""})
            if item.label == DocItemLabel.TITLE and not slide["title"]:
                slide["title"] = item.text
            elif getattr(item, "text", None):
                slide["text"] = f"{slide['text']} {item.text}".strip()
            continue
        if isinstance(item, PictureItem):
            figure_no += 1
            rel = f"figures/{source_id}-fig{figure_no}.png"
            image = item.get_image(doc)
            if image is not None:
                FIGURES.mkdir(parents=True, exist_ok=True)
                image.save(ROOT / "corpus" / rel)
            elements.append({"type": "figure", "page": page, "caption": item.caption_text(doc), "image": rel if image else None})
            continue
        if isinstance(item, TableItem):
            elements.append({**table_element(item), "page": page})
            continue
        if item.label == DocItemLabel.CAPTION and item.self_ref in picture_captions:
            continue  # a figure's caption is already on its figure element
        kind = {DocItemLabel.PAGE_HEADER: "page_header", DocItemLabel.PAGE_FOOTER: "page_footer",
                DocItemLabel.SECTION_HEADER: "heading", DocItemLabel.TITLE: "heading"}.get(item.label, "paragraph")
        element = {"type": kind, "page": page, "text": item.text}
        if kind == "heading":
            element["level"] = 1 if item.label == DocItemLabel.TITLE else getattr(item, "level", 1) + 1
        elements.append(element)
    return [slides[n] for n in sorted(slides)] if is_slides else elements


# --- eCFR XML ------------------------------------------------------------------------------------

HEADING_LEVELS = {"DIV5": 1, "DIV6": 2, "DIV8": 3, "DIV9": 3}


def _text(node: ET.Element) -> str:
    return " ".join("".join(node.itertext()).split())


def ecfr_elements(path: Path) -> list[dict]:
    elements: list[dict] = []

    def walk(node: ET.Element, level: int) -> None:
        for child in node:
            tag = child.tag
            if tag in HEADING_LEVELS:
                walk(child, HEADING_LEVELS[tag])
            elif tag == "HEAD":
                elements.append({"type": "heading", "level": level, "text": _text(child)})
            elif tag in ("P", "FP", "CITA", "AUTH", "SOURCE", "EDNOTE", "NOTE", "SECAUTH"):
                if text := _text(child):
                    elements.append({"type": "paragraph", "text": text})
            elif tag == "TABLE" or child.find(".//TABLE") is not None:
                for table in ([child] if tag == "TABLE" else child.iter("TABLE")):
                    rows = [[_text(c) for c in tr if c.tag in ("TH", "TD")] for tr in table.iter("TR")]
                    has_header = table.find(".//TH") is not None
                    elements.append({"type": "table", "header": rows[0] if has_header and rows else None,
                                     "rows": rows[1:] if has_header else rows})
            else:
                walk(child, level)

    wrapper = ET.Element("wrapper")  # so the root's own HEAD is visited like any other
    wrapper.append(ET.parse(path).getroot())
    walk(wrapper, 1)
    return elements


# --- Main ----------------------------------------------------------------------------------------

def main() -> None:
    catalog = json.loads((SOURCE / "catalog.json").read_text(encoding="utf-8"))["documents"]
    only = set(sys.argv[1:])
    conv = None
    OUT.mkdir(parents=True, exist_ok=True)
    for entry in catalog:
        if only and entry["source_id"] not in only:
            continue
        path = SOURCE / entry["file"]
        fmt = FORMATS[path.suffix]
        start = time.time()
        if fmt == "xml":
            parser, elements, scores = "ecfr-xml", ecfr_elements(path), {}
        else:
            conv = conv or converter()
            result = conv.convert(str(path))
            parser = "docling"
            elements = docling_elements(result.document, entry["source_id"], is_slides=fmt == "pptx")
            report = getattr(result, "confidence", None)
            # Page-level OCR scores, where the parser had to read pixels.
            scores = {n: round(p.ocr_score, 2) for n, p in (report.pages.items() if report else [])
                      if p.ocr_score == p.ocr_score and p.ocr_score > 0}
        for n, element in enumerate(elements, start=1):
            if element.get("page") in scores:
                element["ocr_confidence"] = scores[element["page"]]
            if element.get("page") is None:
                element.pop("page", None)
            elements[n - 1] = {"id": f"e{n}", **element}
        data = {"source_id": entry["source_id"], "file": entry["file"], "format": fmt,
                "parser": parser, "meta": entry["meta"], "elements": elements}
        (OUT / f"{entry['source_id']}.json").write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        print(f"{entry['source_id']:20} {len(elements):4} elements  ({fmt}, {time.time() - start:5.1f}s)", flush=True)


if __name__ == "__main__":
    main()
