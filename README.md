# AP Research Experimental Platform

A reproducible, AI-assisted testing platform for educational research.

## Features

1.  **Strict Question Bank Versioning**: Questions are "frozen" from drafts into locked versions in the database.
2.  **Reproducible Paper Generation**:
    *   **Fixed Mode**: Deterministic set of questions.
    *   **Equivalent Mode**: Randomized selection controlled by a seed (topic + difficulty + isomorphic grouping).
3.  **Deterministic Grading**: No AI involved in scoring.
4.  **AI Wrong-Answer Analysis**:
    *   Uses DeepSeek (or OpenAI-compatible) API.
    *   Provides classified error types and hints (Level 1-3).
    *   **Constraint**: Never solves the problem for the student.
5.  **Isomorphic Practice**:
    *   If a student gets a question wrong, they can practice with a sibling question from the same isomorphic group.
6.  **Repeated Error Detection**:
    *   Alerts the student if they commit the same error type multiple times in a session.

## Setup & Run

### 1. Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Set your DeepSeek API key:
```bash
export DEEPSEEK_API_KEY="sk-..."
```
*(If no key is provided, the system falls back to a deterministic stub for testing.)*

### 3. Initialize Question Bank
The system loads drafts from `questions.json`. You must "freeze" them to create a usable version.
The system attempts to auto-freeze on the first run, or you can trigger it manually:
```bash
# (Optional) Manually freeze via API
curl -X POST http://127.0.0.1:8000/api/admin/freeze
```

### 4. Run Server
```bash
uvicorn backend.main:app --reload
```
Open `http://127.0.0.1:8000`.

## Usage Guide

1.  **Start Test**:
    *   Enter Student ID (e.g., `S101`).
    *   Select Mode: `Fixed` or `Equivalent` (with optional seed).
2.  **Submit**:
    *   Answer questions.
    *   View detailed results.
3.  **Review & Practice**:
    *   For wrong answers, read the AI analysis.
    *   Click **"Practice Similar Question"** to attempt an isomorphic variant.
    *   Look for "Repeated Error" alerts at the top of the results.

## Project Structure
*   `backend/`: FastAPI app, SQLAlchemy models, AI service.
*   `static/`: Vanilla JS frontend.
*   `questions.json`: Draft question source.
*   `ap_research.db`: SQLite database (stores locked questions, papers, submissions, logs).
