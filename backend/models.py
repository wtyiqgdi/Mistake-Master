from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class QuestionBankVersion(Base):
    __tablename__ = "question_bank_versions"
    
    version_id = Column(String, primary_key=True) # e.g. hash
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

class Question(Base):
    __tablename__ = "questions"
    
    db_id = Column(String, primary_key=True, index=True) # uuid (unique question instance id per version)
    original_id = Column(String, index=True)             # id from draft JSON
    version_id = Column(String, ForeignKey("question_bank_versions.version_id"), index=True)
    
    stem = Column(Text)
    type = Column(String) # short_answer, multiple_choice
    options = Column(JSON, nullable=True) # List of dicts
    correct_answer = Column(String)
    topic = Column(String)
    difficulty = Column(Integer)
    reference_outline = Column(Text)
    isomorphic_group = Column(String, index=True)
    knowledge_points = Column(JSON) # List of strings
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('version_id', 'original_id', name='uq_question_version_original'),
    )

class Student(Base):
    __tablename__ = "students"
    
    student_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Paper(Base):
    __tablename__ = "papers"
    
    paper_id = Column(String, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("students.student_id")) # Optional, if paper is pre-generated
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Generation Metadata
    question_bank_version = Column(String, ForeignKey("question_bank_versions.version_id"))
    generation_policy = Column(String) # "FIXED", "EQUIVALENT"
    random_seed = Column(Integer, nullable=True)
    params_json = Column(JSON) # Store specific constraints like topic, difficulty
    
    # The actual questions in this paper (ordered list of db_ids)
    question_ids = Column(JSON) 

class Submission(Base):
    __tablename__ = "submissions"
    
    submission_id = Column(String, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("students.student_id"))
    paper_id = Column(String, ForeignKey("papers.paper_id"))
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    total_score = Column(Float)
    total_questions = Column(Integer)
    
    items = relationship("SubmissionItem", back_populates="submission")

class SubmissionItem(Base):
    __tablename__ = "submission_items"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(String, ForeignKey("submissions.submission_id"))
    question_db_id = Column(String, ForeignKey("questions.db_id"))
    
    student_answer = Column(String)
    is_correct = Column(Boolean)
    score = Column(Float)
    
    # AI Analysis
    error_type = Column(String, nullable=True)
    explanation_text = Column(Text, nullable=True)
    hint_level_requested = Column(Integer, default=0) # Max level requested
    current_hint = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=True) # Full AI output
    
    submission = relationship("Submission", back_populates="items")
    practice_attempts = relationship("IsomorphicPractice", back_populates="original_item")

class IsomorphicPractice(Base):
    __tablename__ = "isomorphic_practices"
    
    practice_id = Column(String, primary_key=True, index=True)
    original_submission_item_id = Column(Integer, ForeignKey("submission_items.id"))
    student_id = Column(String, ForeignKey("students.student_id"))
    
    question_db_id = Column(String, ForeignKey("questions.db_id"))
    student_answer = Column(String)
    is_correct = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    original_item = relationship("SubmissionItem", back_populates="practice_attempts")
