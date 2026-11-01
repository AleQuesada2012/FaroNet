"""Build output/FaroNet-documentacion.pdf: documentation, BOM (annex A) and RFC (annex B).

Requires pandoc and XeLaTeX (TeX Live with fvextra). Run from anywhere:
    python3 scripts/build_docs.py
"""

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "FaroNet-documentacion.pdf"
SCHEMATIC_SVG = "../hardware/schematic/faro-rev7.svg"
HEADER = r"""
\usepackage{fvextra}
\fvset{breaklines=true}
\DefineVerbatimEnvironment{Highlighting}{Verbatim}{breaklines,commandchars=\\\{\}}
"""


def bom_annex() -> str:
    lines = (ROOT / "hardware" / "bom.md").read_text(encoding="utf-8").splitlines()
    # The BOM's own title becomes the annex heading. Annexes are unnumbered,
    # and links to repository files would be dead inside the PDF.
    body = [line + " {.unnumbered}" if line.startswith("#") else line for line in lines[1:]]
    text = "\n".join(["# Anexo A. Lista de materiales (BOM) {.unnumbered}", *body])
    return re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]+\)", r"\1", text)


def rfc_annex() -> str:
    rfc = (ROOT / "docs" / "rfc" / "faronet-rfc.txt").read_text(encoding="ascii")
    return (
        "# Anexo B. RFC FN-1 {.unnumbered}\n\n"
        "Texto ASCII original de `docs/rfc/faronet-rfc.txt`.\n\n"
        "```{=latex}\n\\begin{Verbatim}[fontsize=\\scriptsize]\n"
        f"{rfc}\\end{{Verbatim}}\n```\n"
    )


def main() -> None:
    document = (ROOT / "docs" / "documentacion.md").read_text(encoding="utf-8")
    pdf_schematic = str(ROOT / "hardware" / "schematic" / "faro-rev7.pdf")
    document = document.replace(SCHEMATIC_SVG, pdf_schematic)
    OUTPUT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "documentacion.md"
        source.write_text("\n\n".join([document, bom_annex(), rfc_annex()]), encoding="utf-8")
        header = Path(scratch) / "header.tex"
        header.write_text(HEADER, encoding="utf-8")
        subprocess.run([
            "pandoc", str(source), "-o", str(OUTPUT),
            "--pdf-engine=xelatex", "--toc", "--number-sections",
            "--resource-path", str(ROOT / "docs"), "-H", str(header),
            "-V", "mainfont=Helvetica", "-V", "monofont=Menlo",
            "-V", "geometry:margin=2.2cm", "-V", "colorlinks=true",
            "-V", "documentclass=article", "-V", "fontsize=10pt",
        ], check=True)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
