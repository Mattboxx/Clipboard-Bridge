"""Export the editable social card; requires the optional PyMuPDF developer tool."""

from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/assets/clipboard-bridge-share.svg"
TARGET = SOURCE.with_suffix(".png")


def main():
    with pymupdf.open(SOURCE) as vector:
        with pymupdf.open(stream=vector.convert_to_pdf(), filetype="pdf") as document:
            page = document[0]
            scale = 1200 / page.rect.width
            pixels = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            if (pixels.width, pixels.height) != (1200, 630):
                raise ValueError("Expected a 1200 x 630 social preview")
            pixels.save(TARGET)
    print(TARGET.relative_to(ROOT))


if __name__ == "__main__":
    main()
