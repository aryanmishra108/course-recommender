from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

COURSE_RE = re.compile(r"^[A-Z][A-Z0-9 /&-]{1,14}\s+[FGU]\d{3,4}[A-Z0-9-]*$")
SEC_RE = re.compile(r"^[LTP]\d+$")
DATE_RE = re.compile(r"\b\d{2}/\d{2}\s+(?:FN1|FN2|AN1|AN2|FN|AN)\b")
DAYS = {"M", "T", "W", "Th", "F", "S"}
CORE = {
    "CS F214", "CS F222", "CS F211", "CS F213", "CS F215", "CS F241",
    "CS F212", "CS F351", "CS F372", "CS F363", "CS F301", "CS F364",
    "CS F342", "CS F303"
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def slots(s: str):
    tokens = re.findall(r"Th|M|T|W|F|S|\d+", s)
    pending, out = [], []
    for token in tokens:
        if token in DAYS:
            pending.append(token)
        elif token.isdigit() and pending:
            out.extend([[d, int(token)] for d in pending])
            pending = []
    return out


def timetable():
    path = RAW / "timetable.pdf"
    if not path.exists():
        raise FileNotFoundError(f"Missing required source: {path}")
    doc = pymupdf.open(path)
    rec = {}
    try:
        for pno, page in enumerate(doc, 1):
            lines = [x.strip() for x in page.get_text().splitlines() if x.strip()]
            idx = [i for i, x in enumerate(lines) if COURSE_RE.match(x)]
            for k, i in enumerate(idx):
                end = idx[k + 1] if k + 1 < len(idx) else len(lines)
                block = lines[i:end]
                code = block[0]
                if len(block) < 7:
                    continue
                title = clean(block[1])
                nums = [x for x in block[2:12] if re.fullmatch(r"-|\d+(?:\.\d+)?", x)]
                units = float(nums[4]) if len(nums) >= 5 and nums[4] != "-" else 0
                r = rec.setdefault(code, {
                    "course_code": code, "title": title, "units": units,
                    "department": code.split()[0], "semester": "First Semester 2026-27",
                    "sections": [], "source": {"document": "timetable.pdf", "pages": []}
                })
                r["source"]["pages"].append(pno)
                dates = DATE_RE.findall(" ".join(block))
                if dates:
                    r["midsem"] = dates[0]
                    r["compre"] = dates[1] if len(dates) > 1 else None
                section_idx = [j for j, x in enumerate(block) if SEC_RE.match(x)]
                for z, j in enumerate(section_idx):
                    sb = block[j:(section_idx[z + 1] if z + 1 < len(section_idx) else len(block))]
                    room, sl = None, []
                    for x in sb[1:]:
                        if re.fullmatch(r"\d{4}(?:_[A-Z])?", x):
                            room = x
                        if re.search(r"(?:^|\s)(?:M|T|W|Th|F|S)(?:\s|$)", x) and re.search(r"\d", x):
                            sl = slots(x)
                            if sl:
                                break
                    r["sections"].append({"section": sb[0], "type": sb[0][0], "room": room, "slots": sl})
    finally:
        doc.close()

    out = []
    for r in rec.values():
        r["source"]["pages"] = sorted(set(r["source"]["pages"]))
        c = r["course_code"]
        r["category"] = (
            "CDC" if c in CORE else
            "DEL_CANDIDATE" if c.startswith("CS ") else
            "HUEL_CANDIDATE" if c.startswith(("HSS ", "GS ")) else
            "HUEL_OR_OPEL_CANDIDATE" if c.startswith(("ECON ", "MGTS ")) else
            "OPEL_OR_OTHER"
        )
        r["description"] = ""
        r["prerequisites_raw"] = []
        out.append(r)
    return out


def descriptions(courses):
    path = RAW / "bulletin.pdf"
    if not path.exists():
        return {}
    doc = pymupdf.open(path)
    want = {c["course_code"] for c in courses}
    found = {}
    try:
        for pno, page in enumerate(doc, 1):
            lines = [x.strip() for x in page.get_text().splitlines() if x.strip()]
            for i, x in enumerate(lines):
                if x not in want:
                    continue
                chunk = []
                for y in lines[i + 1:i + 80]:
                    if COURSE_RE.match(y):
                        break
                    chunk.append(y)
                text = clean(" ".join(chunk))
                pre = [clean(m.group(1)) for m in re.finditer(r"Pre[- ]?requisites?\s*:\s*([^\.]+)", text, re.I)]
                found[x] = {"description": text[:6000], "prerequisites_raw": pre,
                            "source": {"document": "bulletin.pdf", "page": pno}}
                want.remove(x)
            if not want:
                break
    finally:
        doc.close()
    return found


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def build_base():
    courses = timetable()
    ds = descriptions(courses)
    for c in courses:
        if c["course_code"] in ds:
            c.update({
                "description": ds[c["course_code"]]["description"],
                "prerequisites_raw": ds[c["course_code"]]["prerequisites_raw"]
            })
            c["source"]["bulletin"] = ds[c["course_code"]]["source"]

    rules = {
        "B.E. Computer Science": {
            "campus": "Pilani", "bulletin_year": "2025-26",
            "foundation_courses": ["BITS F103", "BIO F101", "CHEM F101", "MATH F101", "PHY F101", "BITS F101", "BITS K101", "BITS F111", "BITS F112", "CS F111", "MATH F113", "MATH F102", "EEE F111", "BITS F102", "MATH F211", "BITS F225"],
            "core_courses": sorted(CORE), "core_units": 48, "discipline_elective_units": 12,
            "huel_courses_required": 3, "huel_units_required": 8,
            "semester_pattern_source": {"document": "bulletin.pdf", "page": 217}
        },
        "global_registration": {"first_degree_max_units": 25, "summer_max_courses": 3, "summer_max_units": 10}
    }
    write_json(OUT / "courses_base.json", courses)
    write_json(OUT / "programme_rules.json", rules)
    return courses


def main():
    parser = argparse.ArgumentParser(description="Build the BITS course recommender dataset safely on Windows.")
    parser.add_argument("--handouts-dir", help="Directory containing Part II PDFs.")
    parser.add_argument("--handouts-zip", help="ZIP containing Part II PDFs.")
    args = parser.parse_args()

    # Always rebuild the timetable/bulletin base with UTF-8 output.
    build_base()

    # If a source is supplied, ingest it. Otherwise preserve the committed handout
    # dataset if present, so rerunning this script cannot erase handout integration.
    handouts_json = OUT / "handouts.json"
    if args.handouts_dir or args.handouts_zip:
        if args.handouts_dir and args.handouts_zip:
            raise SystemExit("Use either --handouts-dir or --handouts-zip, not both.")
        from ingest_handouts import main as ingest_main
        source = args.handouts_dir or args.handouts_zip
        processed, unique, errors = ingest_main(source)
        if errors:
            print(f"Warning: {len(errors)} handout files could not be processed.")
    elif handouts_json.exists():
        print("Using existing processed Part II handout dataset; no handouts source was supplied.")
    else:
        print("No Part II handouts supplied. The base dataset will remain valid, but course-specific handout fields will be unavailable.")

    # Merge handout data into the base dataset.
    if handouts_json.exists():
        from merge_handouts import main as merge_main
        merge_main()
    else:
        base = json.loads((OUT / "courses_base.json").read_text(encoding="utf-8"))
        write_json(OUT / "courses.json", base)

    meta = {
        "sources": ["timetable.pdf", "bulletin.pdf", "Academic-Regulations-2023.pdf"],
        "part_ii_handouts_processed": handouts_json.exists(),
        "note": "Course-specific properties are only populated when supported by a Part II handout; otherwise they remain unverified."
    }
    if handouts_json.exists():
        report_path = OUT / "handout_extraction_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            meta.update({"handout_files_processed": report.get("files_processed", report.get("files_found", 0)),
                         "unique_handout_course_codes": report.get("unique_course_codes", 0),
                         "handout_errors": len(report.get("errors", []))})
    write_json(OUT / "metadata.json", meta)
    print("Preprocessing complete.")


if __name__ == "__main__":
    main()
