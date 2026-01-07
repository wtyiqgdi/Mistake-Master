You are a senior full-stack engineer and software architect. 
Your task is to IMPLEMENT a complete, runnable MVP web system.

PROJECT GOAL (MVP)
Build a controlled experimental platform for an educational research project:
1) A predefined question bank (question library) is loaded into the system.
2) The system can generate a test paper from the question bank.
3) Students can answer the test in a web UI and submit.
4) The system automatically grades deterministically (NO AI grading).
5) For each wrong answer ONLY, the system calls an AI module to produce:
   - error type classification (fixed taxonomy)
   - one single-step heuristic hint (no solutions, no final answers)
6) The UI shows total score and per-question feedback; wrong questions show AI analysis + hint.
7) The system logs all submissions and analysis results for later research.

IMPORTANT CONSTRAINTS
- AI MUST NOT generate questions during experiments.
- AI MUST NOT grade answers.
- AI is ONLY used for wrong-answer analysis and hint generation.
- The system must be reproducible. The question bank is fixed and versioned.
- Keep it simple: MVP first, but code must be clean and extendable.

TECH STACK (use exactly this)
- Backend: Python + FastAPI
- Frontend: plain HTML + vanilla JavaScript (no framework)
- Data: SQLite (single local file). Use SQLAlchemy or sqlite3.
- Question bank source: a local JSON file (backend/resources/questions.json) stored in the project.
- AI call: implement a stub function analyze_wrong_answer(); also provide an optional real API integration placeholder with environment variables.

DELIVERABLES
You must output:
A) Folder structure
B) Full backend code (runnable) with clear instructions
C) Full frontend code (runnable)
D) A sample question bank JSON
E) Database schema and migration/initialization steps
F) A runbook: how to install, run, and test
G) A minimal set of test cases / sample requests

FUNCTIONAL DETAILS (MUST IMPLEMENT)
1) Question Bank
- Load from backend/resources/questions.json at startup.
- Provide an endpoint to list questions (for paper generation) but DO NOT expose correct answers to student UI.
- Include question metadata: id, stem, type, correct_answer, tolerance(optional), topic, difficulty, reference_outline, isomorphic_group(optional), knowledge_points(optional).
- Provide a version string for the question bank (e.g., hash of file or manual version field).

2) Paper/Test Generation
- Implement a simple paper generator:
  - mode "fixed": return a predefined list of question_ids
  - mode "random_by_topic": choose N questions from a given topic and difficulty range
- Provide endpoint /api/paper/create that returns paper_id and ordered question list for the student.
- Store the generated paper in DB with timestamp.

3) Student Attempt Flow
- Student opens / (index.html), enters student_id (anonymous code), clicks "Start".
- UI fetches a paper from backend, renders each question with input fields.
- Student submits answers via /api/paper/{paper_id}/submit.

4) Deterministic Grading (NO AI)
- Implement deterministic grading by question type:
  - short_answer: normalize whitespace/case; if numeric compare by float conversion; optional tolerance.
  - multiple_choice: compare chosen option id.
- Return per-question is_correct and score; total score.
- NEVER use AI to determine correctness.

5) AI Wrong-Answer Analysis (ONLY wrong answers)
- If is_correct == false, call analyze_wrong_answer() with:
  - question_stem
  - correct_answer
  - reference_outline
  - student_answer
  - hint_level (default 1)
- Use fixed taxonomy (choose ONE):
  - Conceptual Error
  - Procedural Error
  - Computational Error
  - Strategy Error
  - Careless Error
- Return JSON with:
  - primary_error_type
  - error_explanation (1-2 sentences)
  - hint_level (int)
  - hint (ONE sentence only; no solution; no final answer)
  - recommended_knowledge_points (list)
- IMPORTANT: Provide a strict prompt string inside analyze_wrong_answer() for future real model calls.
- For now, implement a deterministic fallback if AI is unavailable (e.g., generic hint based on knowledge_points).

6) Logging / Research Data
Store in SQLite:
- students (student_id)
- papers (paper_id, created_at, mode, params_json, question_bank_version)
- submissions (submission_id, student_id, paper_id, submitted_at, total_score, total_questions)
- submission_items (submission_id, question_id, student_answer, is_correct, score, error_type, hint_level, hint_text, explanation_text, analysis_json)
Ensure everything is timestamped and reproducible.

7) Security / Privacy (basic)
- Do not store real names.
- student_id is an anonymous code.
- Do not expose correct answers to frontend.
- Only return correct answers to server-side grading.

API ENDPOINTS (MUST IMPLEMENT)
- GET /api/health
- GET /api/question_bank/version
- POST /api/paper/create  (body: {student_id, mode, params})
- GET /api/paper/{paper_id}  (returns questions WITHOUT correct answers)
- POST /api/paper/{paper_id}/submit  (body: {student_id, answers: {qid: answer}})
- GET /api/submission/{submission_id} (returns full graded report for UI)

FRONTEND REQUIREMENTS (MUST IMPLEMENT)
- index.html:
  - input: student_id
  - button: Start Test
  - renders question list with input fields
  - button: Submit
  - shows score summary and per-question results
  - for wrong items, show: error_type + 1-line hint + short explanation
- Use fetch() to call backend API.
- Ensure the frontend never displays correct answers.
- Provide simple but clean layout.

RUN INSTRUCTIONS
- Provide step-by-step commands:
  - create venv
  - pip install -r requirements.txt
  - uvicorn main:app --reload
  - open index.html (or serve static via FastAPI)

QUALITY REQUIREMENTS
- Code must run as-is after copy-paste.
- Use clear naming and comments.
- Validate request payloads using Pydantic.
- Handle missing answers gracefully.
- Return consistent JSON schema.
- Do not leave TODOs except optional real AI API integration.

START OUTPUT NOW
1) First output folder structure.
2) Then provide all backend files content.
3) Then provide frontend files content.
4) Then provide question bank JSON sample.
5) Finally provide runbook and test steps.
