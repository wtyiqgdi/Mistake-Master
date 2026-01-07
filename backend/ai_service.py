import os
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DeepSeek / OpenAI Client
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_API_KEY = os.getenv("LLM_API_KEY") or DEEPSEEK_API_KEY
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

def get_client():
    if not OpenAI or not DEEPSEEK_API_KEY:
        logger.warning("DeepSeek Client not initialized: Missing API Key or library")
        return None
    try:
        return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=12.0)
    except Exception as e:
        logger.error(f"Failed to initialize DeepSeek client: {e}")
        return None

def clean_json_response(content: str) -> str:
    """Removes markdown code blocks if present."""
    # First, try to find the largest JSON block
    match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
        
    match = re.search(r'```\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1).strip()
        
    return content.strip()

def llm_chat_json(provider: str, model: str, system_prompt: str, user_prompt: str, timeout_s: float = 15.0, retries: int = 2) -> Optional[Dict[str, Any]]:
    if not LLM_API_KEY:
        return None
    if provider == "deepseek":
        base = LLM_BASE_URL or DEEPSEEK_BASE_URL
        url = f"{base}/chat/completions"
    elif provider == "openai":
        base = LLM_BASE_URL or "https://api.openai.com/v1"
        url = f"{base}/chat/completions"
    elif provider == "openrouter":
        base = LLM_BASE_URL or "https://openrouter.ai/api/v1"
        url = f"{base}/chat/completions"
    else:
        base = LLM_BASE_URL or DEEPSEEK_BASE_URL
        url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    for _ in range(retries):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    continue
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                cleaned = clean_json_response(content)
                return json.loads(cleaned)
        except Exception:
            continue
    return None

def build_fallback_questions(tp: str, cnt: int) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = [
        {
            "id": "draft_limit_sin_over_x",
            "stem": "Compute the limit: lim_{x->0} (sin x)/x",
            "type": "short_answer",
            "options": [],
            "correct_answer": "1",
            "difficulty": 2,
            "reference_outline": "Use the standard limit sin(x)/x -> 1 as x->0.",
            "knowledge_points": ["limits", "trigonometric limits"],
            "isomorphic_group": "group_limit_sin_over_x",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_derivative_x3",
            "stem": "Compute d/dx of x^3",
            "type": "short_answer",
            "options": [],
            "correct_answer": "3x^2",
            "difficulty": 1,
            "reference_outline": "Power rule: d/dx x^n = n x^{n-1}.",
            "knowledge_points": ["derivatives", "power rule"],
            "isomorphic_group": "group_derivative_power_rule",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_chain_rule_sin_x2",
            "stem": "Compute d/dx of sin(x^2)",
            "type": "short_answer",
            "options": [],
            "correct_answer": "2x cos(x^2)",
            "difficulty": 3,
            "reference_outline": "Chain rule: derivative of sin(u) is cos(u) * du/dx.",
            "knowledge_points": ["chain rule", "trigonometric derivatives"],
            "isomorphic_group": "group_chain_rule_trig",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_integral_x_0_1",
            "stem": "Compute the definite integral: ∫_0^1 x dx",
            "type": "short_answer",
            "options": [],
            "correct_answer": "1/2",
            "difficulty": 2,
            "reference_outline": "Antiderivative of x is x^2/2; evaluate at bounds.",
            "knowledge_points": ["definite integrals", "Fundamental Theorem of Calculus"],
            "isomorphic_group": "group_integral_linear",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_mcq_derivative_ln",
            "stem": "Which of the following is d/dx (ln x) for x>0?",
            "type": "multiple_choice",
            "options": [
                {"id": "A", "text": "1/x"},
                {"id": "B", "text": "x"},
                {"id": "C", "text": "ln x"},
                {"id": "D", "text": "0"}
            ],
            "correct_answer": "A",
            "difficulty": 1,
            "reference_outline": "Derivative of natural log is 1/x.",
            "knowledge_points": ["logarithmic derivatives"],
            "isomorphic_group": "group_derivative_log",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_product_rule_x_ex",
            "stem": "Compute d/dx of x e^x",
            "type": "short_answer",
            "options": [],
            "correct_answer": "e^x + x e^x",
            "difficulty": 2,
            "reference_outline": "Product rule: (uv)' = u'v + uv'.",
            "knowledge_points": ["product rule", "exponential derivatives"],
            "isomorphic_group": "group_product_rule",
            "topic": tp or "Calculus"
        },
        {
            "id": "draft_limit_e",
            "stem": "Evaluate lim_{n->∞} (1 + 1/n)^n",
            "type": "short_answer",
            "options": [],
            "correct_answer": "e",
            "difficulty": 3,
            "reference_outline": "Definition of e via compound interest limit.",
            "knowledge_points": ["limits", "number e"],
            "isomorphic_group": "group_limit_e",
            "topic": tp or "Calculus"
        }
    ]
    res: List[Dict[str, Any]] = []
    for i in range(cnt):
        base = dict(pool[i % len(pool)])
        base["id"] = f"{base['id']}_{i+1}"
        res.append(base)
    return res

def _normalize_ai_analysis(raw: Dict[str, Any], hint_level: int, reference_outline: str) -> Dict[str, Any]:
    allowed = {
        "Conceptual Error",
        "Procedural Error",
        "Computational Error",
        "Strategy Error",
        "Careless Error",
    }

    et = raw.get("primary_error_type")
    if not isinstance(et, str):
        et = "Conceptual Error"
    et = et.strip()
    if et not in allowed:
        s = et.lower()
        if "procedure" in s or "process" in s or "step" in s:
            et = "Procedural Error"
        elif "compute" in s or "calculation" in s or "arithmetic" in s:
            et = "Computational Error"
        elif "strategy" in s or "approach" in s:
            et = "Strategy Error"
        elif "careless" in s or "typo" in s or "slip" in s:
            et = "Careless Error"
        else:
            et = "Conceptual Error"

    exp = raw.get("error_explanation")
    if not isinstance(exp, str) or not exp.strip():
        exp = "Your answer does not match the expected reasoning."
    exp = exp.strip()

    hint = raw.get("hint")
    if not isinstance(hint, str) or not hint.strip():
        base = reference_outline.strip() if isinstance(reference_outline, str) and reference_outline.strip() else "the relevant concept"
        hint = f"Re-check the key idea in the reference outline about {base}."
    hint = hint.strip()

    kps = raw.get("recommended_knowledge_points")
    if kps is None:
        kps_list: List[str] = []
    elif isinstance(kps, list):
        kps_list = [str(x).strip() for x in kps if x is not None and str(x).strip()]
    elif isinstance(kps, str):
        kps_list = [p.strip() for p in kps.split(",") if p.strip()]
    else:
        kps_list = [str(kps).strip()] if str(kps).strip() else []

    return {
        "primary_error_type": et,
        "error_explanation": exp,
        "hint_level": int(hint_level),
        "hint": hint,
        "recommended_knowledge_points": kps_list,
    }

def analyze_wrong_answer(
    question_stem: str, 
    correct_answer: str, 
    reference_outline: str, 
    student_answer: str, 
    hint_level: int = 1
) -> Dict[str, Any]:
    """
    Analyzes a wrong answer to produce error classification and a hint.
    """
    
    system_prompt = (
        "You are an expert tutor. Analyze the student's wrong answer and give feedback without solving. "
        "Return strict JSON only."
    )
    user_prompt = (
        "Task: Analyze the following wrong answer.\n\n"
        f"Question: {question_stem}\n"
        f"Correct Answer: {correct_answer}\n"
        f"Reference Outline: {reference_outline}\n"
        f"Student Answer: {student_answer}\n"
        f"Requested Hint Level: {hint_level} (1=Subtle, 2=Moderate, 3=Strong)\n\n"
        "Constraints:\n"
        '1) "primary_error_type" must be exactly one of: "Conceptual Error", "Procedural Error", "Computational Error", "Strategy Error", "Careless Error".\n'
        "2) error_explanation: 1-2 sentences.\n"
        "3) hint: exactly ONE sentence; do NOT reveal the answer; do NOT solve.\n"
        "4) recommended_knowledge_points: list 1-5 short phrases.\n\n"
        "Output JSON:\n"
        '{'
        '"primary_error_type":"...",'
        '"error_explanation":"...",'
        f'"hint_level":{int(hint_level)},'
        '"hint":"...",'
        '"recommended_knowledge_points":["..."]'
        '}'
    )

    base_timeout = 18.0
    for attempt in range(3):
        llm_res = llm_chat_json(LLM_PROVIDER, LLM_MODEL, system_prompt, user_prompt, timeout_s=base_timeout, retries=1)
        if isinstance(llm_res, dict) and llm_res:
            return _normalize_ai_analysis(llm_res, hint_level, reference_outline)
        time.sleep(0.6 * (2 ** attempt))

    student_s = student_answer.strip() if isinstance(student_answer, str) else ""
    if not student_s:
        et = "Strategy Error"
    else:
        et = "Conceptual Error"
        try:
            ca = float(str(correct_answer).strip())
            sa = float(student_s)
            if abs(ca - sa) < 1e-6:
                et = "Careless Error"
            elif abs(ca - sa) / (abs(ca) + 1e-6) < 0.05:
                et = "Computational Error"
        except Exception:
            pass

    ref = reference_outline.strip() if isinstance(reference_outline, str) and reference_outline.strip() else "the relevant concept"
    if hint_level == 1:
        hint = f"Revisit the core concept mentioned in the reference outline about {ref}."
    elif hint_level == 2:
        hint = f"Identify the specific rule/step in the reference outline about {ref} that your answer violates."
    else:
        hint = f"Compare your answer with the reference outline about {ref} and locate the first incorrect step."

    return {
        "primary_error_type": et,
        "error_explanation": "Your answer does not align with the expected reasoning based on the reference outline.",
        "hint_level": int(hint_level),
        "hint": hint,
        "recommended_knowledge_points": [ref] if ref else ["Review Topic"],
    }

def generate_draft_questions(topic: str, count: int = 5, allow_fallback: bool = True) -> List[Dict[str, Any]]:
    """
    Generates draft questions via AI.
    Admin only.
    """
    def build_fallback_questions(tp: str, cnt: int) -> List[Dict[str, Any]]:
        pool: List[Dict[str, Any]] = [
            {
                "id": "draft_limit_sin_over_x",
                "stem": "Compute the limit: lim_{x->0} (sin x)/x",
                "type": "short_answer",
                "options": [],
                "correct_answer": "1",
                "difficulty": 2,
                "reference_outline": "Use the standard limit sin(x)/x -> 1 as x->0.",
                "knowledge_points": ["limits", "trigonometric limits"],
                "isomorphic_group": "group_limit_sin_over_x",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_derivative_x3",
                "stem": "Compute d/dx of x^3",
                "type": "short_answer",
                "options": [],
                "correct_answer": "3x^2",
                "difficulty": 1,
                "reference_outline": "Power rule: d/dx x^n = n x^{n-1}.",
                "knowledge_points": ["derivatives", "power rule"],
                "isomorphic_group": "group_derivative_power_rule",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_chain_rule_sin_x2",
                "stem": "Compute d/dx of sin(x^2)",
                "type": "short_answer",
                "options": [],
                "correct_answer": "2x cos(x^2)",
                "difficulty": 3,
                "reference_outline": "Chain rule: derivative of sin(u) is cos(u) * du/dx.",
                "knowledge_points": ["chain rule", "trigonometric derivatives"],
                "isomorphic_group": "group_chain_rule_trig",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_integral_x_0_1",
                "stem": "Compute the definite integral: ∫_0^1 x dx",
                "type": "short_answer",
                "options": [],
                "correct_answer": "1/2",
                "difficulty": 2,
                "reference_outline": "Antiderivative of x is x^2/2; evaluate at bounds.",
                "knowledge_points": ["definite integrals", "Fundamental Theorem of Calculus"],
                "isomorphic_group": "group_integral_linear",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_mcq_derivative_ln",
                "stem": "Which of the following is d/dx (ln x) for x>0?",
                "type": "multiple_choice",
                "options": [
                    {"id": "A", "text": "1/x"},
                    {"id": "B", "text": "x"},
                    {"id": "C", "text": "ln x"},
                    {"id": "D", "text": "0"}
                ],
                "correct_answer": "A",
                "difficulty": 1,
                "reference_outline": "Derivative of natural log is 1/x.",
                "knowledge_points": ["logarithmic derivatives"],
                "isomorphic_group": "group_derivative_log",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_product_rule_x_ex",
                "stem": "Compute d/dx of x e^x",
                "type": "short_answer",
                "options": [],
                "correct_answer": "e^x + x e^x",
                "difficulty": 2,
                "reference_outline": "Product rule: (uv)' = u'v + uv'.",
                "knowledge_points": ["product rule", "exponential derivatives"],
                "isomorphic_group": "group_product_rule",
                "topic": tp or "Calculus"
            },
            {
                "id": "draft_limit_e",
                "stem": "Evaluate lim_{n->∞} (1 + 1/n)^n",
                "type": "short_answer",
                "options": [],
                "correct_answer": "e",
                "difficulty": 3,
                "reference_outline": "Definition of e via compound interest limit.",
                "knowledge_points": ["limits", "number e"],
                "isomorphic_group": "group_limit_e",
                "topic": tp or "Calculus"
            }
        ]
        res: List[Dict[str, Any]] = []
        for i in range(cnt):
            base = dict(pool[i % len(pool)])
            base["id"] = f"{base['id']}_{i+1}"
            res.append(base)
        return res
    
    system_prompt = "Return strict JSON only."
    user_prompt = (
        f'Generate {count} high-quality questions for the subject/topic "{topic}". '
        'Return JSON: {"questions":[{id, stem, type, options?, correct_answer, difficulty, reference_outline, knowledge_points, isomorphic_group, topic}...]}. '
        'type in {"short_answer","multiple_choice"}; options only for multiple_choice; difficulty must be 1-5; topic should be the provided subject/topic.'
    )
    llm_res = llm_chat_json(LLM_PROVIDER, LLM_MODEL, system_prompt, user_prompt, timeout_s=15.0, retries=2)
    if llm_res and isinstance(llm_res.get("questions"), list) and llm_res["questions"]:
        return llm_res["questions"]
    if isinstance(llm_res, list) and llm_res:
        return llm_res
    
    client = get_client()
    if not client:
        if allow_fallback:
            return build_fallback_questions(topic, count)
        else:
            raise RuntimeError("DeepSeek client not initialized or API key missing.")
    
    if count > 6:
        aggregated: List[Dict[str, Any]] = []
        remaining = count
        while remaining > 0:
            batch = 6 if remaining >= 6 else remaining
            aggregated.extend(generate_draft_questions(topic, batch, allow_fallback))
            remaining -= batch
        return aggregated
        
    prompt = f"""
    Generate {count} high-quality questions on subject/topic: "{topic}".
    
    Structure the response as a JSON object with a single key "questions" containing the array.
    
    Each question object must have:
    - id: string (e.g. "draft_1")
    - stem: string
    - type: "short_answer" or "multiple_choice"
    - options: array of {{id, text}} (if MC)
    - correct_answer: string
    - difficulty: int (1-5)
    - reference_outline: string
    - knowledge_points: array of strings
    - isomorphic_group: string (random group id)
    
    Example JSON:
    {{
      "questions": [
        {{ "id": "q1", "stem": "...", "type": "short_answer", ... }}
      ]
    }}
    """
    
    # Retry small number of times to reduce transient timeouts
    attempts = 2
    for i in range(attempts):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a JSON generator. Return strict JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                top_p=0.9
            )
            content = response.choices[0].message.content
            logger.info(f"AI Generation Raw Response (attempt {i+1}): {content}")
            
            content = clean_json_response(content)
            data = None
            try:
                data = json.loads(content)
            except Exception as parse_err:
                logger.error(f"Parse failed on attempt {i+1}: {parse_err}")
                data = None
            
            # Handle if wrapped in a key
            if data and "questions" in data:
                if isinstance(data["questions"], list) and len(data["questions"]) > 0:
                    return data["questions"]
            elif isinstance(data, list) and len(data) > 0:
                return data
        except Exception as e:
            logger.error(f"DeepSeek call failed on attempt {i+1}: {e}")
            continue
    
    # If we reach here, generation failed
    if allow_fallback:
        logger.info("Using curated calculus fallback.")
        return build_fallback_questions(topic, count)
    else:
        raise RuntimeError("DeepSeek generation error: Request timed out.")
