#!/usr/bin/env python3
"""
generate_redline.py — Generate Word track-changes DOCX from NDA review output.

Uses python-docx + lxml to produce proper w:ins / w:del XML so counterparties
can accept/reject individual changes in Word's Review mode.

Usage:
  python3 generate_redline.py --source path/to/nda.docx --issues issues.json
  python3 generate_redline.py --source path/to/nda.docx --interactive

Environment:
  NDA_SKILL_REVIEWER_NAME  — Author name shown in track changes (default: "Reviewer")
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from lxml import etree
except ImportError:
    print("ERROR: python-docx and lxml are required. Run: pip install python-docx lxml")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────

AUTHOR = os.environ.get("NDA_SKILL_REVIEWER_NAME", "Reviewer")
DATE_STR = f"{date.today().isoformat()}T00:00:00Z"
_id_counter = [0]


def _nid() -> str:
    _id_counter[0] += 1
    return str(_id_counter[0])


# ── XML helpers ────────────────────────────────────────────────────────────────

def _norm_run(text: str, bold: bool = False) -> "etree._Element":
    r = OxmlElement("w:r")
    if bold:
        rpr = OxmlElement("w:rPr")
        rpr.append(OxmlElement("w:b"))
        r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


def _del_run(text: str) -> "etree._Element":
    d = OxmlElement("w:del")
    d.set(qn("w:id"), _nid())
    d.set(qn("w:author"), AUTHOR)
    d.set(qn("w:date"), DATE_STR)
    r = OxmlElement("w:r")
    dt = OxmlElement("w:delText")
    dt.set(qn("xml:space"), "preserve")
    dt.text = text
    r.append(dt)
    d.append(r)
    return d


def _ins_run(text: str) -> "etree._Element":
    i = OxmlElement("w:ins")
    i.set(qn("w:id"), _nid())
    i.set(qn("w:author"), AUTHOR)
    i.set(qn("w:date"), DATE_STR)
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    i.append(r)
    return i


def _add_para(doc: Document, *segments: tuple) -> None:
    """
    Add a paragraph with mixed segments.
    segments: (type, text) where type is 'n' (normal), 'b' (bold), 'd' (delete), 'i' (insert)
    """
    p = OxmlElement("w:p")
    for typ, text in segments:
        if typ == "n":
            p.append(_norm_run(text))
        elif typ == "b":
            p.append(_norm_run(text, bold=True))
        elif typ == "d":
            p.append(_del_run(text))
        elif typ == "i":
            p.append(_ins_run(text))
    doc.element.body.insert(len(doc.element.body) - 1, p)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_heading(text, level=level)
    return p


# ── Standard redline positions ─────────────────────────────────────────────────

STANDARD_REDLINES = [
    {
        "id": "ci-temporal",
        "clause": "CI Definition — Temporal Scope",
        "priority": "HIGH",
        "original": "whether before or after the date of this Agreement",
        "redlined": "on or after the date of this Agreement",
        "rationale": (
            "Pre-signing disclosures are typically governed by a separate NDA or implied "
            "confidentiality obligations. Including them here creates unbounded historical liability."
        ),
    },
    {
        "id": "ci-oral",
        "clause": "CI Definition — Oral Disclosures",
        "priority": "HIGH",
        "original": "(no written confirmation requirement for oral disclosures)",
        "redlined": "For oral disclosures, Confidential Information shall include only information "
                    "designated as confidential at the time of disclosure and confirmed in writing "
                    "within ten (10) business days thereafter.",
        "rationale": (
            "Without a written confirmation window, any oral statement could retrospectively "
            "become Confidential Information, creating practical enforcement issues."
        ),
    },
    {
        "id": "permitted-advisors",
        "clause": "Permitted Disclosees — Professional Advisors",
        "priority": "HIGH",
        "original": "directors, officers, and employees",
        "redlined": "directors, officers, employees, and professional advisors "
                    "(including legal counsel, accountants, and financial advisors) who are "
                    "bound by professional obligations of confidentiality",
        "rationale": (
            "Professional advisors routinely need access to evaluate a transaction. "
            "Excluding them creates operational friction and is non-standard."
        ),
    },
    {
        "id": "return-destruction-election",
        "clause": "Return / Destruction — Party Election",
        "priority": "MEDIUM",
        "original": "with the Disclosing Party's written consent, will either (a) return … or (b) destroy",
        "redlined": "at the Receiving Party's election, either (a) return … or (b) destroy",
        "rationale": (
            "Requiring Disclosing Party consent for destruction removes the Receiving Party's "
            "ability to meet its own data-management obligations. Market standard is election."
        ),
    },
    {
        "id": "return-retention-exception",
        "clause": "Return / Destruction — Retention Exception",
        "priority": "MEDIUM",
        "original": "(no exception for automated backup systems)",
        "redlined": "Notwithstanding the foregoing, the Receiving Party shall not be required to "
                    "return or destroy copies of Confidential Information held in automated backup "
                    "systems, provided such copies are not accessible in the normal course of "
                    "business and are overwritten in the Receiving Party's normal backup cycle.",
        "rationale": (
            "Without this carveout, complete return/destruction is technically impossible "
            "and creates residual legal exposure for the Receiving Party."
        ),
    },
    {
        "id": "term",
        "clause": "Confidentiality Tail — Term",
        "priority": "MEDIUM",
        "original": "three (3) years",
        "redlined": "two (2) years",
        "rationale": (
            "Two years is market standard for general commercial NDAs. Three years may be "
            "appropriate for highly sensitive technical information — adjust based on context."
        ),
    },
]


# ── Document extraction ────────────────────────────────────────────────────────

def extract_text_from_docx(path: Path) -> str:
    """Extract plain text from a DOCX file."""
    import zipfile
    try:
        with zipfile.ZipFile(str(path)) as z:
            with z.open("word/document.xml") as f:
                xml = f.read().decode("utf-8")
                text = re.sub(r"<[^>]+>", " ", xml)
                return re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        return f"(extraction failed: {e})"


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_text_from_docx(path)
    elif suffix in (".md", ".txt"):
        try:
            return path.read_text()
        except OSError as e:
            return f"(read failed: {e})"
    else:
        try:
            return path.read_text(errors="replace")
        except OSError as e:
            return f"(read failed: {e})"


# ── Redline document generation ────────────────────────────────────────────────

def generate_redline_doc(
    source_path: Path,
    issues: list[dict],
    output_path: Path | None = None,
) -> Path:
    """
    Generate a track-changes DOCX.

    issues: list of dicts with keys: id, clause, priority, original, redlined, rationale
    """
    doc = Document()
    today = date.today().strftime("%Y%m%d")
    reviewer = AUTHOR.replace(" ", "_")

    if output_path is None:
        output_path = source_path.parent / f"NDA_Redlined_{reviewer}_{today}.docx"

    # Cover heading
    doc.add_heading("NDA — Redlined Version", 0)
    doc.add_paragraph(f"Reviewer: {AUTHOR} | Date: {date.today().isoformat()}")
    doc.add_paragraph(f"Source: {source_path.name}")
    doc.add_paragraph("")

    doc.add_heading("Track Changes Summary", 1)
    doc.add_paragraph(
        f"This document contains {len(issues)} proposed change(s). "
        "Items marked in red are deletions; items in green are insertions. "
        "Please accept or reject each change using Word's Review → Accept/Reject feature."
    )
    doc.add_paragraph("")

    # One section per issue
    for issue in issues:
        _add_heading(doc, f"[{issue['priority']}] {issue['clause']}", level=2)

        # Rationale line
        doc.add_paragraph(f"Rationale: {issue['rationale']}")

        # Proposed change with track-change markup
        _add_para(doc,
            ("b", "Proposed change: "),
            ("d", issue["original"]),
            ("n", " → "),
            ("i", issue["redlined"]),
        )
        doc.add_paragraph("")

    # Signature block placeholder
    doc.add_heading("Signature Block", 1)
    doc.add_paragraph("[Parties' signature lines — unchanged from original]")

    try:
        doc.save(str(output_path))
    except OSError as e:
        print(f"ERROR: Could not save output file {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NDA redline DOCX with track changes")
    parser.add_argument("--source",      required=True, help="Path to source NDA file (.docx/.md)")
    parser.add_argument("--issues",      default="",    help="Path to JSON issues file")
    parser.add_argument("--output",      default="",    help="Output DOCX path (auto-named if omitted)")
    parser.add_argument("--all-standard",action="store_true",
                        help="Apply all standard redline positions without interactive selection")
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    if not source.exists():
        print(f"ERROR: Source file not found: {source}")
        sys.exit(1)

    # Load issues
    if args.issues:
        issues_path = Path(args.issues).expanduser()
        try:
            issues = json.loads(issues_path.read_text())
        except FileNotFoundError:
            print(f"ERROR: Issues file not found: {issues_path}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"ERROR: Issues file is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.all_standard:
        issues = STANDARD_REDLINES
    else:
        # Default to all standard positions
        print(f"No --issues file provided. Applying {len(STANDARD_REDLINES)} standard redline positions.")
        issues = STANDARD_REDLINES

    output = Path(args.output).expanduser() if args.output else None
    out_path = generate_redline_doc(source, issues, output)

    print(f"✅ Redlined document generated: {out_path}")
    print(f"   Changes applied: {len(issues)}")
    for issue in issues:
        print(f"   [{issue['priority']}] {issue['clause']}")


if __name__ == "__main__":
    main()
