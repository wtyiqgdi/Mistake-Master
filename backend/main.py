import json
import os
import uuid
import hashlib
import random
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from . import models, schemas, database, ai_service

# Initialize DB
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AP Research Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _load_draft_bank() -> List[Dict[str, Any]]:
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions.json")
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    return [q for q in data if isinstance(q, dict)]

def _save_draft_bank(data: List[Dict[str, Any]]) -> None:
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions.json")
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _mc_option_id(i: int) -> str:
    if 0 <= i < 26:
        return chr(ord("A") + i)
    return str(i + 1)

def _difficulty_bucket(v: Any) -> str:
    if isinstance(v, int):
        if 1 <= v <= 5:
            return str(v)
        return "other"
    if isinstance(v, str):
        s = v.strip().lower()
        mapping = {
            "easy": "1",
            "medium": "3",
            "hard": "5",
        }
        return mapping.get(s, "other")
    return "unknown"

def _normalize_topic_and_difficulty(q: Dict[str, Any], fallback_topic: str) -> Dict[str, Any]:
    topic = q.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        q["topic"] = fallback_topic

    diff = q.get("difficulty")
    if isinstance(diff, str):
        s = diff.strip().lower()
        mapping = {"easy": 1, "medium": 3, "hard": 5}
        if s in mapping:
            q["difficulty"] = mapping[s]
    elif isinstance(diff, float):
        q["difficulty"] = int(diff)

    return q

def _normalize_question(q: Dict[str, Any], fallback_topic: str) -> Dict[str, Any]:
    if "id" not in q or q.get("id") is None or (isinstance(q.get("id"), str) and not q["id"].strip()):
        q["id"] = uuid.uuid4().hex
    elif isinstance(q["id"], int):
        q["id"] = str(q["id"])

    _normalize_topic_and_difficulty(q, fallback_topic)

    q_type = q.get("type")
    if not isinstance(q_type, str) or not q_type.strip():
        q["type"] = "short_answer"
        q_type = "short_answer"
    else:
        q_type = q_type.strip()
        q["type"] = q_type

    if q_type == "multiple_choice":
        opts = q.get("options")
        if isinstance(opts, list):
            if len(opts) > 0 and all(isinstance(o, str) for o in opts):
                mapped = [{"id": _mc_option_id(i), "text": o} for i, o in enumerate(opts)]
                q["options"] = mapped
            elif len(opts) > 0 and all(isinstance(o, dict) for o in opts):
                normalized_opts = []
                for i, o in enumerate(opts):
                    oid = o.get("id")
                    text = o.get("text")
                    if not isinstance(oid, str) or not oid.strip():
                        oid = _mc_option_id(i)
                    if not isinstance(text, str):
                        text = "" if text is None else str(text)
                    normalized_opts.append({"id": oid, "text": text})
                q["options"] = normalized_opts
        if not isinstance(q.get("options"), list):
            q["options"] = []

        ca = q.get("correct_answer")
        if isinstance(ca, str):
            ca_s = ca.strip()
        else:
            ca_s = "" if ca is None else str(ca).strip()

        for opt in q.get("options", []):
            if isinstance(opt, dict) and isinstance(opt.get("text"), str) and opt.get("text") == ca_s:
                q["correct_answer"] = opt.get("id", ca_s)
                break
        else:
            q["correct_answer"] = ca_s
    else:
        ca = q.get("correct_answer")
        if not isinstance(ca, str):
            q["correct_answer"] = "" if ca is None else str(ca)

    kp = q.get("knowledge_points")
    if kp is None:
        q["knowledge_points"] = []
    elif isinstance(kp, str):
        parts = [p.strip() for p in kp.split(",")]
        q["knowledge_points"] = [p for p in parts if p]
    elif isinstance(kp, list):
        q["knowledge_points"] = [str(x) for x in kp if x is not None and str(x).strip()]
    else:
        q["knowledge_points"] = [str(kp)]

    for k in ["stem", "reference_outline", "isomorphic_group", "topic"]:
        if k in q and q[k] is not None and not isinstance(q[k], str):
            q[k] = str(q[k])

    return q

# ==========================================
# MODULE 1: QUESTION BANK (Draft -> Locked)
# ==========================================

@app.post("/api/admin/generate_drafts")
def generate_drafts(topic: str, count: int = 5, source: str = "auto"):
    """
    Admin: Generate draft questions
    source:
      - "ai": strictly use DeepSeek; on failure returns 500 with error message
      - "offline": use curated calculus offline set
      - "auto": try AI, fall back to offline on error
    """
    try:
        if source == "offline":
            res = ai_service.build_fallback_questions(topic, count)
        elif source == "ai":
            res = ai_service.generate_draft_questions(topic, count, allow_fallback=False)
        else:
            res = ai_service.generate_draft_questions(topic, count, allow_fallback=True)
        if isinstance(res, list):
            fallback_topic = topic.strip() if isinstance(topic, str) and topic.strip() else "未分类"
            return [_normalize_topic_and_difficulty(q, fallback_topic) if isinstance(q, dict) else q for q in res]
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DeepSeek generation error: {str(e)}")

@app.get("/api/admin/draft_stats")
def draft_stats():
    data = _load_draft_bank()
    total = len(data)

    by_topic: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_difficulty: Dict[str, int] = {}
    missing_topic = 0
    missing_type = 0
    missing_difficulty = 0

    for q in data:
        topic = q.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            missing_topic += 1
            topic = "未分类"
        by_topic[topic] = by_topic.get(topic, 0) + 1

        q_type = q.get("type")
        if not isinstance(q_type, str) or not q_type.strip():
            missing_type += 1
            q_type = "unknown"
        by_type[q_type] = by_type.get(q_type, 0) + 1

        if "difficulty" not in q:
            missing_difficulty += 1
        bucket = _difficulty_bucket(q.get("difficulty"))
        by_difficulty[bucket] = by_difficulty.get(bucket, 0) + 1

    def _sorted(d: Dict[str, int]):
        return [{"key": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: (-kv[1], str(kv[0])))]

    return {
        "total": total,
        "by_topic": _sorted(by_topic),
        "by_type": _sorted(by_type),
        "by_difficulty": _sorted(by_difficulty),
        "missing": {
            "topic": missing_topic,
            "type": missing_type,
            "difficulty": missing_difficulty,
        },
    }

@app.get("/api/admin/drafts")
def list_drafts(
    q: Optional[str] = None,
    topic: Optional[str] = None,
    type: Optional[str] = None,
    difficulty: Optional[int] = None,
    offset: int = 0,
    limit: int = 50,
):
    data = _load_draft_bank()
    items = []
    for item in data:
        display_topic = item.get("topic") if isinstance(item.get("topic"), str) and item.get("topic").strip() else "未分类"
        display_type = item.get("type") if isinstance(item.get("type"), str) and item.get("type").strip() else "unknown"
        display_diff = item.get("difficulty")
        if isinstance(display_diff, str):
            try:
                display_diff_int = int(display_diff)
            except Exception:
                display_diff_int = None
        elif isinstance(display_diff, int):
            display_diff_int = display_diff
        else:
            display_diff_int = None

        if topic and display_topic != topic:
            continue
        if type and display_type != type:
            continue
        if difficulty is not None and display_diff_int != difficulty:
            continue
        if q:
            needle = q.strip().lower()
            hay = (item.get("stem") or "")
            if not isinstance(hay, str) or needle not in hay.lower():
                continue

        items.append(item)

    topics = sorted({(it.get("topic") if isinstance(it.get("topic"), str) and it.get("topic").strip() else "未分类") for it in data})
    types = sorted({(it.get("type") if isinstance(it.get("type"), str) and it.get("type").strip() else "unknown") for it in data})

    total = len(items)
    offset = max(0, offset)
    limit = max(1, min(200, limit))
    page = items[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "items": page, "topics": topics, "types": types}

@app.get("/api/admin/drafts/{draft_id}")
def get_draft(draft_id: str):
    data = _load_draft_bank()
    for item in data:
        if str(item.get("id")) == str(draft_id):
            return item
    raise HTTPException(status_code=404, detail="Draft not found")

@app.post("/api/admin/drafts")
def create_draft(payload: Dict[str, Any]):
    data = _load_draft_bank()
    fallback_topic = payload.get("topic") if isinstance(payload.get("topic"), str) and payload.get("topic").strip() else "未分类"
    q_obj = _normalize_question(dict(payload), fallback_topic)
    existing_ids = {str(q.get("id")) for q in data if isinstance(q, dict) and q.get("id") is not None}
    if q_obj["id"] in existing_ids:
        q_obj["id"] = f"{q_obj['id']}_{uuid.uuid4().hex[:4]}"
    data.append(q_obj)
    _save_draft_bank(data)
    return q_obj

@app.put("/api/admin/drafts/{draft_id}")
def update_draft(draft_id: str, payload: Dict[str, Any]):
    data = _load_draft_bank()
    idx = None
    for i, item in enumerate(data):
        if str(item.get("id")) == str(draft_id):
            idx = i
            break
    if idx is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    fallback_topic = payload.get("topic") if isinstance(payload.get("topic"), str) and payload.get("topic").strip() else (
        data[idx].get("topic") if isinstance(data[idx].get("topic"), str) and data[idx].get("topic").strip() else "未分类"
    )
    merged = dict(payload)
    merged["id"] = str(draft_id)
    q_obj = _normalize_question(merged, fallback_topic)
    data[idx] = q_obj
    _save_draft_bank(data)
    return q_obj

@app.delete("/api/admin/drafts/{draft_id}")
def delete_draft(draft_id: str):
    data = _load_draft_bank()
    new_data = [q for q in data if str(q.get("id")) != str(draft_id)]
    if len(new_data) == len(data):
        raise HTTPException(status_code=404, detail="Draft not found")
    _save_draft_bank(new_data)
    return {"deleted": 1}

@app.post("/api/admin/drafts/normalize")
def normalize_drafts(default_topic: str = "Calculus"):
    data = _load_draft_bank()
    fallback_topic = default_topic.strip() if isinstance(default_topic, str) and default_topic.strip() else "未分类"

    changed = 0
    topic_filled = 0
    options_fixed = 0
    correct_fixed = 0
    difficulty_fixed = 0

    for i, item in enumerate(data):
        before = json.dumps(item, ensure_ascii=False, sort_keys=True)
        before_topic_missing = not (isinstance(item.get("topic"), str) and item.get("topic").strip())
        before_opts = item.get("options")
        before_ca = item.get("correct_answer")
        before_diff = item.get("difficulty")

        _normalize_question(item, fallback_topic)

        if before_topic_missing and isinstance(item.get("topic"), str) and item.get("topic").strip():
            topic_filled += 1
        if before_opts != item.get("options"):
            options_fixed += 1
        if before_ca != item.get("correct_answer"):
            correct_fixed += 1
        if before_diff != item.get("difficulty"):
            difficulty_fixed += 1

        after = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed += 1
        data[i] = item

    _save_draft_bank(data)
    return {
        "total": len(data),
        "changed": changed,
        "topic_filled": topic_filled,
        "options_fixed": options_fixed,
        "correct_answer_fixed": correct_fixed,
        "difficulty_fixed": difficulty_fixed,
    }

@app.post("/api/admin/save_drafts")
def save_drafts(questions: List[Dict[str, Any]]):
    """
    Appends new questions to questions.json (Draft Bank).
    """
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions.json")
    
    current_data = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                current_data = json.load(f)
            except json.JSONDecodeError:
                pass
    
    # Append new questions
    # Ensure IDs are unique? For drafts, we might just append.
    # Ideally, we should check ID collision or regenerate IDs.
    # For MVP, let's assume AI generates distinct IDs or we fix them.
    
    # Fix IDs to ensure uniqueness if needed (simple append with prefix)
    existing_ids = {q["id"] for q in current_data}
    
    added_count = 0
    for q in questions:
        fallback_topic = q.get("topic") if isinstance(q.get("topic"), str) and q.get("topic").strip() else "未分类"
        q_obj = _normalize_question(dict(q), fallback_topic)
        if q_obj["id"] in existing_ids:
            q_obj["id"] = f"{q_obj['id']}_{uuid.uuid4().hex[:4]}"
        existing_ids.add(q_obj["id"])
        current_data.append(q_obj)
        added_count += 1
        
    with open(file_path, "w") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)
        
    return {"message": "Drafts saved successfully", "added_count": added_count}

@app.post("/api/admin/freeze")
def freeze_question_bank(db: Session = Depends(get_db)):
    """
    Freezes the current questions.json into the SQLite DB as a new version.
    """
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="questions.json not found")
        
    with open(file_path, "r") as f:
        content = f.read()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="questions.json is not valid JSON")
        data = [q for q in data if isinstance(q, dict)]
        data = [q for q in data if not q.get("is_fallback")]
        if not data:
            raise HTTPException(status_code=400, detail="questions.json is empty or only contains fallback items")
        
    # Generate Version ID (Hash of content)
    version_id = hashlib.md5(content.encode()).hexdigest()[:8]
    
    # Check if exists
    existing = db.query(models.QuestionBankVersion).filter_by(version_id=version_id).first()
    if existing:
        return {"message": "Version already exists", "version_id": version_id}
        
    # Create Version
    new_version = models.QuestionBankVersion(version_id=version_id, description="Imported from questions.json")
    db.add(new_version)
    
    # Bulk Insert Questions
    count = 0
    for q in data:
        # Create a unique DB ID for this version of the question
        db_id = str(uuid.uuid4())
        fallback_topic = q.get("topic") if isinstance(q.get("topic"), str) and q.get("topic").strip() else "未分类"
        q_obj = _normalize_question(dict(q), fallback_topic)
        diff = q_obj.get("difficulty")
        if not isinstance(diff, int) or not (1 <= diff <= 5):
            diff = 3

        db_q = models.Question(
            db_id=db_id,
            original_id=str(q_obj.get("id", "")),
            version_id=version_id,
            stem=str(q_obj.get("stem", "")),
            type=str(q_obj.get("type", "short_answer")),
            options=q_obj.get("options"),
            correct_answer=str(q_obj.get("correct_answer", "")),
            topic=str(q_obj.get("topic", fallback_topic)),
            difficulty=diff,
            reference_outline=q_obj.get("reference_outline"),
            isomorphic_group=q_obj.get("isomorphic_group"),
            knowledge_points=q_obj.get("knowledge_points", [])
        )
        db.add(db_q)
        count += 1
        
    db.commit()
    return {"message": "Question bank frozen successfully", "version_id": version_id, "count": count}

@app.get("/api/question_bank/latest_version")
def get_latest_version(db: Session = Depends(get_db)):
    v = db.query(models.QuestionBankVersion).order_by(models.QuestionBankVersion.created_at.desc()).first()
    if not v:
        try:
            return freeze_question_bank(db)
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(status_code=404, detail="No question bank versions found")
    count = db.query(models.Question).filter_by(version_id=v.version_id).count()
    if count == 0:
        try:
            return freeze_question_bank(db)
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(status_code=404, detail="No usable question bank versions found")
    return {"version_id": v.version_id}

# ==========================================
# MODULE 2: PAPER GENERATION
# ==========================================

@app.post("/api/paper/create", response_model=schemas.PaperResponse)
def create_paper(request: schemas.PaperCreateRequest, db: Session = Depends(get_db)):
    # Ensure student exists
    student = db.query(models.Student).filter(models.Student.student_id == request.student_id).first()
    if not student:
        student = models.Student(student_id=request.student_id)
        db.add(student)
        db.commit()

    # Get Latest Bank Version
    version_res = get_latest_version(db)
    if isinstance(version_res, dict): # Handle direct call vs API call
        version_id = version_res["version_id"]
    else:
        version_id = version_res.version_id

    selected_questions = []
    
    if request.mode == "fixed":
        if request.fixed_question_ids:
            for orig_id in request.fixed_question_ids:
                q = db.query(models.Question).filter_by(version_id=version_id, original_id=orig_id).first()
                if q: selected_questions.append(q)
        else:
            selected_questions = db.query(models.Question).filter_by(version_id=version_id).all()
            
    elif request.mode == "equivalent":
        query = db.query(models.Question).filter_by(version_id=version_id)
        if request.topic:
            query = query.filter(models.Question.topic == request.topic)
        if request.difficulty:
            query = query.filter(models.Question.difficulty == request.difficulty)
            
        candidates = query.all()
        
        rng = random.Random(request.seed if request.seed is not None else None)
        
        groups = {}
        for q in candidates:
            g = q.isomorphic_group or "ungrouped_" + q.original_id
            if g not in groups: groups[g] = []
            groups[g].append(q)
            
        group_keys = sorted(list(groups.keys())) # Sort for reproducibility before shuffle
        rng.shuffle(group_keys)
        
        selected_questions = []
        for g in group_keys[:request.count]:
            selected_questions.append(rng.choice(groups[g]))
    
    if not selected_questions:
        raise HTTPException(status_code=400, detail="No questions available in the current question bank. Please generate and freeze questions first.")
            
    # Save Paper
    paper_id = str(uuid.uuid4())
    paper = models.Paper(
        paper_id=paper_id,
        student_id=request.student_id,
        question_bank_version=version_id,
        generation_policy=request.mode,
        random_seed=request.seed,
        params_json=request.model_dump(exclude={"student_id"}),
        question_ids=[q.db_id for q in selected_questions]
    )
    db.add(paper)
    db.commit()
    
    # Map to Schema
    qs_out = []
    for q in selected_questions:
        qs_out.append(schemas.QuestionPublic(
            id=q.db_id,
            original_id=q.original_id,
            stem=q.stem,
            type=q.type,
            options=q.options,
            topic=q.topic,
            difficulty=q.difficulty,
            reference_outline=q.reference_outline,
            isomorphic_group=q.isomorphic_group,
            knowledge_points=q.knowledge_points
        ))
        
    return schemas.PaperResponse(
        paper_id=paper_id,
        question_bank_version=version_id,
        questions=qs_out
    )

@app.get("/api/paper/{paper_id}", response_model=schemas.PaperResponse)
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    paper = db.query(models.Paper).filter_by(paper_id=paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    qs_out = []
    for q_db_id in paper.question_ids:
        q = db.query(models.Question).filter_by(db_id=q_db_id).first()
        if q:
            qs_out.append(schemas.QuestionPublic(
                id=q.db_id,
                original_id=q.original_id,
                stem=q.stem,
                type=q.type,
                options=q.options,
                topic=q.topic,
                difficulty=q.difficulty,
                reference_outline=q.reference_outline,
                isomorphic_group=q.isomorphic_group,
                knowledge_points=q.knowledge_points
            ))
            
    return schemas.PaperResponse(
        paper_id=paper_id,
        question_bank_version=paper.question_bank_version,
        questions=qs_out
    )

# ==========================================
# MODULE 4: GRADING (Deterministic)
# ==========================================

def check_answer_logic(q: models.Question, ans: str) -> bool:
    if not ans: return False
    correct = q.correct_answer
    
    if q.type == "multiple_choice":
        return ans.strip().upper() == correct.strip().upper()
    elif q.type == "short_answer":
        # Numeric check
        try:
            return abs(float(ans) - float(correct)) < 1e-6
        except:
            return ans.strip().lower() == correct.strip().lower()
    return False

@app.post("/api/paper/{paper_id}/submit", response_model=schemas.SubmissionResponse)
def submit_paper(paper_id: str, request: schemas.SubmitRequest, db: Session = Depends(get_db)):
    paper = db.query(models.Paper).filter_by(paper_id=paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    submission_id = str(uuid.uuid4())
    total_score = 0.0
    results = []
    
    # Track errors for Repeated Error Detection
    current_errors = [] # (type, kp)
    
    for q_db_id in paper.question_ids:
        q = db.query(models.Question).filter_by(db_id=q_db_id).first()
        if not q: continue
        
        student_ans = request.answers.get(q_db_id, "")
        is_correct = check_answer_logic(q, student_ans)
        score = 1.0 if is_correct else 0.0
        total_score += score
        
        # Create Item
        item = models.SubmissionItem(
            submission_id=submission_id,
            question_db_id=q_db_id,
            student_answer=student_ans,
            is_correct=is_correct,
            score=score
        )
        
        analysis_res = None
        
        # MODULE 5: AI WRONG-ANSWER ANALYSIS
        if not is_correct:
            # Default hint level 1 for initial feedback
            analysis = ai_service.analyze_wrong_answer(
                question_stem=q.stem,
                correct_answer=q.correct_answer,
                reference_outline=q.reference_outline,
                student_answer=student_ans,
                hint_level=1
            )
            
            item.error_type = analysis["primary_error_type"]
            item.explanation_text = analysis["error_explanation"]
            item.hint_level_requested = 1
            item.current_hint = analysis["hint"]
            item.analysis_json = analysis
            
            analysis_res = schemas.AIAnalysisResult(**analysis)
            
            # Track for repeated error detection
            current_errors.append({
                "type": item.error_type,
                "kps": q.knowledge_points
            })
            
        db.add(item)
        db.flush() # Get ID
        
        # Check if practice is available (has isomorphic group with >1 items)
        can_practice = False
        if not is_correct and q.isomorphic_group:
            count_group = db.query(models.Question).filter_by(
                version_id=paper.question_bank_version, 
                isomorphic_group=q.isomorphic_group
            ).count()
            if count_group > 1:
                can_practice = True

        results.append(schemas.SubmissionItemResponse(
            id=item.id,
            question_id=q_db_id,
            student_answer=student_ans,
            is_correct=is_correct,
            score=score,
            error_analysis=analysis_res,
            can_practice=can_practice
        ))
        
    submission = models.Submission(
        submission_id=submission_id,
        student_id=request.student_id,
        paper_id=paper_id,
        total_score=total_score,
        total_questions=len(results)
    )
    db.add(submission)
    db.commit()
    
    # MODULE 7: REPEATED ERROR DETECTION
    repeated_alerts = []
    # Fetch previous submissions
    prev_subs = db.query(models.Submission).filter(
        models.Submission.student_id == request.student_id,
        models.Submission.submission_id != submission_id
    ).all()
    
    # Aggregate history
    history_error_types = {}
    history_kps = {}
    
    for sub in prev_subs:
        for it in sub.items:
            if not it.is_correct and it.error_type:
                history_error_types[it.error_type] = history_error_types.get(it.error_type, 0) + 1
                # Need to load Q to get KPs if not stored in Item. 
                # For efficiency, we rely on current session for immediate feedback, 
                # or do a deeper query. Let's do a simple check on current session duplicates first.
    
    # Check duplicates WITHIN this session + history
    # (Simplified for MVP: Check if same error type appears >= 2 times in THIS paper)
    current_type_counts = {}
    for err in current_errors:
        et = err["type"]
        current_type_counts[et] = current_type_counts.get(et, 0) + 1
        if current_type_counts[et] == 2:
            repeated_alerts.append(f"Notice: You made a '{et}' twice in this test. Review recommended.")
            
    return schemas.SubmissionResponse(
        submission_id=submission_id,
        total_score=total_score,
        total_questions=len(results),
        results=results,
        repeated_errors=repeated_alerts
    )

@app.post("/api/submission/items/{item_id}/hint", response_model=schemas.AIAnalysisResult)
def upgrade_hint(item_id: int, request: schemas.HintUpgradeRequest, db: Session = Depends(get_db)):
    item = db.query(models.SubmissionItem).filter(models.SubmissionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Submission item not found")
    if item.is_correct:
        raise HTTPException(status_code=400, detail="Hint is only available for wrong answers")

    submission = item.submission
    if not submission:
        submission = db.query(models.Submission).filter(models.Submission.submission_id == item.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.student_id != request.student_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    q = db.query(models.Question).filter(models.Question.db_id == item.question_db_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    analysis = ai_service.analyze_wrong_answer(
        question_stem=q.stem,
        correct_answer=q.correct_answer,
        reference_outline=q.reference_outline,
        student_answer=item.student_answer or "",
        hint_level=request.hint_level,
    )

    item.error_type = analysis["primary_error_type"]
    item.explanation_text = analysis["error_explanation"]
    item.hint_level_requested = request.hint_level
    item.current_hint = analysis["hint"]
    item.analysis_json = analysis
    db.add(item)
    db.commit()

    return schemas.AIAnalysisResult(**analysis)

# ==========================================
# MODULE 6: ISOMORPHIC PRACTICE
# ==========================================

@app.post("/api/practice/create", response_model=schemas.PracticeResponse)
def create_practice(request: schemas.PracticeRequest, db: Session = Depends(get_db)):
    # Find original wrong item
    item = db.query(models.SubmissionItem).filter(models.SubmissionItem.id == request.original_submission_item_id).first()
    if not item or item.is_correct:
        raise HTTPException(status_code=400, detail="Invalid item for practice")
        
    # Get original question
    orig_q = db.query(models.Question).filter_by(db_id=item.question_db_id).first()
    if not orig_q or not orig_q.isomorphic_group:
        raise HTTPException(status_code=400, detail="No isomorphic group found")
        
    # Find siblings in same version
    siblings = db.query(models.Question).filter(
        models.Question.version_id == orig_q.version_id,
        models.Question.isomorphic_group == orig_q.isomorphic_group,
        models.Question.db_id != orig_q.db_id
    ).all()
    
    if not siblings:
        raise HTTPException(status_code=404, detail="No other questions in this group")
        
    # Pick one random
    practice_q = random.choice(siblings)
    
    # Create Practice Record
    practice_id = str(uuid.uuid4())
    prac = models.IsomorphicPractice(
        practice_id=practice_id,
        original_submission_item_id=item.id,
        student_id=request.student_id,
        question_db_id=practice_q.db_id
    )
    db.add(prac)
    db.commit()
    
    return schemas.PracticeResponse(
        practice_id=practice_id,
        question=schemas.QuestionPublic(
            id=practice_q.db_id,
            original_id=practice_q.original_id,
            stem=practice_q.stem,
            type=practice_q.type,
            options=practice_q.options,
            topic=practice_q.topic,
            difficulty=practice_q.difficulty,
            reference_outline=practice_q.reference_outline,
            isomorphic_group=practice_q.isomorphic_group,
            knowledge_points=practice_q.knowledge_points
        )
    )

@app.post("/api/practice/{practice_id}/submit", response_model=schemas.PracticeResultResponse)
def submit_practice(practice_id: str, request: schemas.PracticeSubmitRequest, db: Session = Depends(get_db)):
    prac = db.query(models.IsomorphicPractice).filter_by(practice_id=practice_id).first()
    if not prac:
        raise HTTPException(status_code=404, detail="Practice session not found")
        
    q = db.query(models.Question).filter_by(db_id=prac.question_db_id).first()
    
    is_correct = check_answer_logic(q, request.answer)
    
    prac.student_answer = request.answer
    prac.is_correct = is_correct
    db.commit()
    
    feedback = "Great job! You corrected your mistake." if is_correct else "Still incorrect. Keep reviewing."
    
    return schemas.PracticeResultResponse(
        is_correct=is_correct,
        correct_answer=q.correct_answer if is_correct else "Hidden", # Only reveal if correct? Or never?
        feedback=feedback
    )

@app.get("/@vite/client")
def vite_client():
    return Response(status_code=204)

@app.head("/@vite/client")
def vite_client_head():
    return Response(status_code=204)

@app.get("/%40vite/client")
def vite_client_encoded():
    return Response(status_code=204)

@app.head("/%40vite/client")
def vite_client_encoded_head():
    return Response(status_code=204)

# Serve Static
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=False), name="static_assets")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
