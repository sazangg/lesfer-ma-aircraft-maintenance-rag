"""Copy a page range of a PDF into a new PDF, unchanged.

AC 43.13-1B is 646 pages. The corpus keeps chapter 7 (pages 313 to 380 of the PDF), which is
what the shop's procedures cite, so the repository stays small and parsing stays quick.

    uv run --group parse python scripts/excerpt_pdf.py AC_43.13-1B_w-chg1.pdf corpus/source/faa/ac/ac-43.13-1b-chapter-7.pdf 313 380
"""

from __future__ import annotations

import sys

import pypdfium2 as pdfium


def main() -> None:
    source, target, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    src = pdfium.PdfDocument(source)
    out = pdfium.PdfDocument.new()
    out.import_pages(src, list(range(first - 1, last)))
    out.save(target)
    print(f"{target}: pages {first} to {last} of {len(src)}")


if __name__ == "__main__":
    main()
