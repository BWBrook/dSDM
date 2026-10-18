#!/usr/bin/env python3
"""Apply the repo's minimal, reproducible Word review layout.

This postprocessor changes OOXML formatting only.  It keeps document text,
figures, relationships, and all non-document package members byte-for-byte
unchanged, and fails if the text or image inventory changes.
"""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
NS = {"w": W_NS}


def w(tag: str) -> str:
    return f"{W}{tag}"


def ensure(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag, NS)
    if child is None:
        child = ET.SubElement(parent, w(tag.split("}")[-1]))
    return child


def set_attr(element: ET.Element, name: str, value: str) -> bool:
    key = w(name)
    if element.attrib.get(key) == value:
        return False
    element.attrib[key] = value
    return True


def text_signature(document_xml: bytes) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    root = ET.fromstring(document_xml)
    texts: list[str] = []
    breaks: list[tuple[str, str]] = []
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in {"t", "delText", "instrText", "delInstrText"}:
            texts.append(element.text or "")
        elif local == "br":
            breaks.append((local, element.attrib.get(w("type"), "")))
    return tuple(texts), tuple(breaks)


def package_signature(payloads: dict[str, bytes]) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    names = tuple(payloads)
    media = tuple(
        (name, hashlib.sha256(payloads[name]).hexdigest())
        for name in names
        if name.startswith("word/media/")
    )
    return names, media


def set_section_layout(root: ET.Element) -> int:
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("DOCX document.xml has no body")
    sect_pr = body.find("w:sectPr", NS)
    if sect_pr is None:
        sect_pr = ET.SubElement(body, w("sectPr"))

    changed = 0
    pg_sz = ensure(sect_pr, w("pgSz"))
    changed += set_attr(pg_sz, "w", "11906")
    changed += set_attr(pg_sz, "h", "16838")
    pg_mar = ensure(sect_pr, w("pgMar"))
    changed += set_attr(pg_mar, "top", "1134")
    changed += set_attr(pg_mar, "bottom", "1134")
    changed += set_attr(pg_mar, "left", "1417")
    changed += set_attr(pg_mar, "right", "1417")
    return changed


def set_table_paragraph_compact(paragraph: ET.Element) -> int:
    changed = 0
    p_pr = ensure(paragraph, w("pPr"))
    spacing = ensure(p_pr, w("spacing"))
    changed += set_attr(spacing, "line", "240")
    changed += set_attr(spacing, "lineRule", "auto")
    changed += set_attr(spacing, "before", "0")
    changed += set_attr(spacing, "after", "0")

    for run in paragraph.findall(".//w:r", NS):
        r_pr = ensure(run, w("rPr"))
        size = ensure(r_pr, w("sz"))
        changed += set_attr(size, "val", "20")
        size_cs = ensure(r_pr, w("szCs"))
        changed += set_attr(size_cs, "val", "20")
    return changed


def add_keep_next(paragraph: ET.Element) -> int:
    p_pr = ensure(paragraph, w("pPr"))
    keep_next = p_pr.find("w:keepNext", NS)
    if keep_next is not None:
        return 0
    ET.SubElement(p_pr, w("keepNext"))
    return 1


def widen_s11_columns(table: ET.Element) -> int:
    rows = table.findall("w:tr", NS)
    if not rows:
        return 0
    first_cells = rows[0].findall("w:tc", NS)
    header = "".join(first_cells[0].itertext()).strip() if first_cells else ""
    grid = table.find("w:tblGrid", NS)
    cols = grid.findall("w:gridCol", NS) if grid is not None else []
    if header != "Species" or len(first_cells) != 6 or len(cols) != 6:
        return 0

    # Keep the existing full table width while giving species and the two
    # conventional columns enough room for their labels.
    target = ["1800", "1400", "1400", "1400", "1650", "1650"]
    changed = 0
    for column, width in zip(cols, target):
        changed += set_attr(column, "w", width)
    for row in rows:
        cells = row.findall("w:tc", NS)
        if len(cells) != len(target):
            continue
        for cell, width in zip(cells, target):
            tc_pr = ensure(cell, w("tcPr"))
            tc_w = ensure(tc_pr, w("tcW"))
            changed += set_attr(tc_w, "type", "dxa")
            changed += set_attr(tc_w, "w", width)
    return changed


def set_caption_page_breaks(root: ET.Element) -> int:
    targets = ("Table 2.", "Table S10a.", "Table S10b.", "Table S10c.", "Table S11.")
    changed = 0
    for paragraph in root.findall(".//w:p", NS):
        text = " ".join("".join(paragraph.itertext()).split())
        if not text.startswith(targets):
            continue
        p_pr = ensure(paragraph, w("pPr"))
        if p_pr.find("w:pageBreakBefore", NS) is None:
            ET.SubElement(p_pr, w("pageBreakBefore"))
            changed += 1
    return changed


def set_tables(root: ET.Element) -> int:
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("DOCX document.xml has no body")
    children = list(body)
    changed = 0
    for index, table in enumerate(body.findall("w:tbl", NS)):
        rows = table.findall("w:tr", NS)
        for row_index, row in enumerate(rows):
            tr_pr = ensure(row, w("trPr"))
            if tr_pr.find("w:cantSplit", NS) is None:
                ET.SubElement(tr_pr, w("cantSplit"))
                changed += 1
            if row_index == 0 and tr_pr.find("w:tblHeader", NS) is None:
                ET.SubElement(tr_pr, w("tblHeader"))
                changed += 1
            for paragraph in row.findall(".//w:p", NS):
                changed += set_table_paragraph_compact(paragraph)
                if row_index == 0:
                    changed += add_keep_next(paragraph)

        changed += widen_s11_columns(table)

        # Keep a caption or subcaption attached to the first header row.
        table_position = children.index(table)
        for previous in reversed(children[max(0, table_position - 4) : table_position]):
            if previous.tag != w("p"):
                continue
            previous_text = " ".join("".join(previous.itertext()).split())
            if previous_text.startswith("Table ") or previous_text.startswith("("):
                changed += add_keep_next(previous)
                break
    return changed


def rewrite_docx(path: Path) -> tuple[int, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path, "r") as source:
        members = source.namelist()
        payloads = {member: source.read(member) for member in members}

    document_key = "word/document.xml"
    if document_key not in payloads:
        raise ValueError(f"{path} has no {document_key}")
    before_content = text_signature(payloads[document_key])
    before_package = package_signature(payloads)
    root = ET.fromstring(payloads[document_key])
    changed = set_section_layout(root) + set_tables(root) + set_caption_page_breaks(root)
    payloads[document_key] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if text_signature(payloads[document_key]) != before_content:
        raise ValueError(f"text or page-break content changed while formatting {path}")
    if package_signature(payloads) != before_package:
        raise ValueError(f"image/package inventory changed while formatting {path}")

    if changed == 0:
        return changed, before_content

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=path.parent) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for member in members:
                target.writestr(member, payloads[member])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return changed, before_content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", action="append", required=True, type=Path)
    args = parser.parse_args()
    for path in args.docx:
        changed, content = rewrite_docx(path)
        print(f"Formatted {path}: {changed} OOXML changes; preserved {len(content[0])} text nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
