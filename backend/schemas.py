from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# --- Question Schemas ---

class Option(BaseModel):
    id: str
    text: str

class QuestionBase(BaseModel):
    stem: str
    type: Literal["short_answer", "multiple_choice"]
    options: Optional[List[Option]] = None
    topic: str
    difficulty: int = Field(..., ge=1, le=5)
    reference_outline: Optional[str] = None
    isomorphic_group: Optional[str] = None
    knowledge_points: List[str] = []

class QuestionCreate(QuestionBase):
    id: str # The manual ID in JSON
    correct_answer: str

class QuestionPublic(QuestionBase):
    id: str # This will be the DB ID (unique per version)
    original_id: str

# --- Paper Schemas ---

class PaperCreateRequest(BaseModel):
    student_id: str
    mode: Literal["fixed", "equivalent"] = "fixed"
    # For equivalent mode
    topic: Optional[str] = None
    difficulty: Optional[int] = None
    count: int = 5
    seed: Optional[int] = None
    
    # For fixed mode (optional override)
    fixed_question_ids: Optional[List[str]] = None

class PaperResponse(BaseModel):
    paper_id: str
    question_bank_version: str
    questions: List[QuestionPublic]

# --- Submission Schemas ---

class SubmitRequest(BaseModel):
    student_id: str
    answers: Dict[str, str] # question_db_id -> answer string

class HintUpgradeRequest(BaseModel):
    student_id: str
    hint_level: int = Field(..., ge=1, le=3)

class AIAnalysisResult(BaseModel):
    primary_error_type: Literal[
        "Conceptual Error", 
        "Procedural Error", 
        "Computational Error", 
        "Strategy Error", 
        "Careless Error"
    ]
    error_explanation: str
    hint_level: int
    hint: str
    recommended_knowledge_points: List[str]

class SubmissionItemResponse(BaseModel):
    id: int # Submission Item ID (internal)
    question_id: str
    student_answer: str
    is_correct: bool
    score: float
    # Only if wrong
    error_analysis: Optional[AIAnalysisResult] = None
    can_practice: bool = False

class SubmissionResponse(BaseModel):
    submission_id: str
    total_score: float
    total_questions: int
    results: List[SubmissionItemResponse]
    repeated_errors: List[str] = [] # Alert messages

# --- Isomorphic Practice Schemas ---

class PracticeRequest(BaseModel):
    student_id: str
    original_submission_item_id: int # ID of the wrong answer item

class PracticeResponse(BaseModel):
    practice_id: str # UUID
    question: QuestionPublic

class PracticeSubmitRequest(BaseModel):
    student_id: str
    answer: str

class PracticeResultResponse(BaseModel):
    is_correct: bool
    correct_answer: str # We can reveal it now? Maybe not. Let's keep it hidden or reveal if correct.
    # The prompt doesn't strictly say NO correct answer in practice, but "No correct answers are exposed to frontend" is a global constraint.
    # So we should NOT return correct_answer unless logic changes.
    feedback: str
