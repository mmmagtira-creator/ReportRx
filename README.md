# ReportRx

A thesis-aligned prototype web app for **Adverse Drug Reaction (ADR) report analysis**. Users input free-text Taglish ADR reports and the system extracts structured predictions — drug mentions, reactions, onset timing, confidence scores, and status assignments — using the rule-based span-graph extraction model developed for this thesis.

---

## Setup

### 1. Create and activate virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```


### 3. Run the app

```bash
uvicorn app.main:app --reload
```

The app will be available at **http://127.0.0.1:8000**

---

## How It Works

1. **Input** — The user types a free-text ADR report into the text box. Reports may be in English, Tagalog, or mixed Taglish.

2. **Analysis** — The backend passes the text through the rule-based extraction pipeline:
   - **Drug Detection** — Identifies pharmaceutical drug and medicine mentions (brand names and generic names common in Philippine pharmacovigilance).
   - **Reaction Extraction** — Uses the thesis span-graph model (`extractor.py`, `patterns.py`) to detect adverse reaction mentions in both English and Tagalog.
   - **Onset Detection** — Extracts temporal cues indicating when the reaction occurred relative to drug intake.

3. **Confidence & Status** — A calibrated confidence score is computed from the extraction quality. The status is assigned based on configurable thresholds:
   - **Accepted** (≥ 0.70) — High-confidence extraction with clear drug-reaction pair.
   - **Needs Review** (≥ 0.40) — Partial or ambiguous extraction requiring manual review.
   - **Abstain** (< 0.40) — Insufficient evidence to form a confident prediction.

4. **Persistence** — Every analyzed report is stored in a local SQLite database (`app/data/reportrx.db`), with auto-incrementing sequential case IDs (`case_00001`, `case_00002`, …) that persist across server restarts.

5. **Export** — The accumulated results can be exported as a CSV file matching the format of the thesis pipeline's `predictions.csv`.

---

## Features

- **Single-page UI** — Type a report, click *Analyze Report*, see structured results in a scrollable table
- **Disclaimer wall** — On first visit, a prominent notice reminds users that results are for demonstration only and are not medical advice
- **Rule-based extraction model** — Leverages the thesis codebase's pattern-matching engine for drug, reaction, and onset span extraction
- **Calibrated confidence scoring** — Temperature-scaled confidence values that reflect extraction quality
- **Status assignment** — Automatic classification into *Accepted*, *Needs Review*, or *Abstain* based on configurable thresholds
- **Persistent storage** — SQLite database survives server restarts; all reports are immediately visible on page reload
- **Sequential case IDs** — `case_00001`, `case_00002`, … auto-incrementing and gap-free
- **CSV export** — One-click download of all analyzed reports
- **Clear All** — Reset button with a styled confirmation dialog; wipes all reports and resets the case counter
- **Sub-millisecond inference** — Local model predictions complete in under 1ms

---

## API Endpoints

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/`               | Main page (single-page UI)           |
| POST   | `/api/analyze`    | Analyze a single ADR report          |
| GET    | `/api/reports`    | List all persisted reports (JSON)    |
| DELETE | `/api/reports`    | Clear all reports and reset counter  |
| GET    | `/api/export/csv` | Download all reports as CSV          |
| GET    | `/api/health`     | Health check                         |

### POST `/api/analyze`

**Request:**
```json
{
  "text_report": "Nag-take ako ng amoxicillin. Later nagka-rash ako at hilo."
}
```

**Response:**
```json
{
  "case_id": "case_00001",
  "text_report": "Nag-take ako ng amoxicillin. Later nagka-rash ako at hilo.",
  "drug_mention": "amoxicillin",
  "reaction_mention": "rash | hilo",
  "onset": "Later",
  "raw_confidence": 0.7283,
  "status": "Accepted",
  "latency_ms": 0.4703
}
```

---

## Project Structure

```
app/
├── main.py                              # FastAPI entry point
├── config.py                            # Centralised settings & thresholds
├── db.py                                # SQLite persistence layer
├── api/
│   └── routes.py                        # API endpoint definitions
├── services/
│   └── analyzers/
│       ├── base.py                      # Provider interface (AnalysisResult)
│       ├── local_fallback_provider.py   # Rule-based extraction model
│       └── orchestrator.py              # Analysis pipeline coordinator
├── templates/
│   └── index.html                       # Single-page UI template
├── static/
│   ├── styles.css                       # Stylesheet
│   └── app.js                           # Frontend logic
└── data/
    └── reportrx.db                      # Auto-created SQLite database
```

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn
- **Frontend:** Jinja2 templates, vanilla JavaScript, CSS
- **Storage:** SQLite (WAL mode) via stdlib `sqlite3`
- **Model:** Rule-based span-graph extractor (thesis codebase: `extractor.py`, `patterns.py`, `preprocessing.py`, `schema.py`)
