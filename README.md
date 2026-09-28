# BITS Academic Course Recommender — Postman Round 2

A Streamlit MVP implementing the requirement-first course recommendation flow from the supplied Postman brief, using the BITS Bulletin, timetable, Academic Regulations, and the supplied Part II course handouts.

## Core flow

`Student Profile → Academic Requirement Analysis → Eligibility → Natural-Language Preference Matching → Policy Validation → Recommendations`

## Included data

The committed `data/processed/` directory already contains the processed Part II handout dataset, so the app can be run immediately. The source handout PDFs themselves are **not** bundled into this project ZIP because the source archive is very large.

The processed dataset contains course-specific information only where supported by the handouts. Missing information is left unverified rather than invented.

## Run on Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

**You do not need to run preprocessing to use the included dataset.**

## Rebuild the dataset from the 540-handout ZIP

`preprocess.py` is now Windows-safe and UTF-8 based. It uses `pymupdf` rather than the deprecated `fitz` import, and it will not erase the committed handout dataset when no new handout source is supplied.

If your ZIP is at:

```text
C:\Users\Aryan\Downloads\dataset\handouts(1).zip
```

run:

```bat
python scripts\preprocess.py --handouts-zip "C:\Users\Aryan\Downloads\dataset\handouts(1).zip"
```

Or, if you extract the PDFs first:

```bat
python scripts\preprocess.py --handouts-dir "C:\Users\Aryan\Downloads\dataset\handouts"
```

The pipeline will:

1. rebuild the timetable/bulletin base dataset;
2. extract all Part II PDFs;
3. merge duplicate/shared course codes;
4. preserve course-specific attendance/evaluation/midsem/compre/project/quiz/lab/makeup information when stated;
5. merge the handout records into `data/processed/courses.json`;
6. write an extraction report showing processed files and errors.

For image-only PDFs, OCR is attempted when PyMuPDF cannot extract enough text. OCR additionally requires a working Tesseract installation on the machine.

## Important data behavior

- A handout is stronger evidence for course-specific policies than generic course metadata.
- If a handout does not state an attendance or makeup rule, the app does not invent one.
- Multiple handouts for the same course are consolidated rather than shown as duplicate courses.
- Courses appearing only in the handout collection can be retained as unscheduled records if they are absent from the timetable.
- Student transcript/history is not supplied; completed/current courses are therefore entered manually in the dashboard.

## Tests

```bat
pytest -q
```

The current test suite passes 3/3 tests.
