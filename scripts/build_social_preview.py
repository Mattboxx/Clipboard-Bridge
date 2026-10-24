"""Export the editable social card; requires the optional PyMuPDF developer tool."""

from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
ASSETS = (("clipboard-bridge-cover.svg", 1200, 630),
          ("clipboard-bridge-cover-mobile.svg", 750, 750))


def main():
    for filename, width, height in ASSETS:
        source = ROOT / "docs/assets" / filename
        target = source.with_suffix(".png")
        with pymupdf.open(source) as vector:
            with pymupdf.open(stream=vector.convert_to_pdf(), filetype="pdf") as document:
                page = document[0]
                scale = width / page.rect.width
                pixels = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                if (pixels.width, pixels.height) != (width, height):
                    raise ValueError(f"Expected a {width} x {height} cover")
                pixels.save(target)
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
