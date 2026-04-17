from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from .ai_policy import get_ai_access_context

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None


AI_NEXT_QUESTION_PROMPT = """You are choosing the single next best clarification question for an analytics SaaS.
The upload has already been profiled, and a question pack already exists.
Based on the current answers, choose ONLY one next unanswered question key that will most improve chart planning.
Return strict JSON: {"next_key": "snake_case_key_or_empty", "reason": "short"}
If no more question is needed, return {"next_key": "", "reason": "enough confidence"}.
Prioritise questions that clarify:
- actual vs target pairing
- time axis
- primary business goal
- main measures
- best breakdowns
- output breadth

PROFILE:
{profile_json}

QUESTIONS:
{questions_json}

CURRENT ANSWERS:
{answers_json}
"""


def _answer_present(question: Dict[str, Any], answers: Dict[str, Any]) -> bool:
    key = question.get("key")
    if not key:
        return False
    val = answers.get(key)
    if isinstance(val, list):
        return bool([x for x in val if str(x).strip()])
    return bool(str(val).strip()) if val is not None else False


def _heuristic_next_key(profile: Dict[str, Any], questions: List[Dict[str, Any]], answers: Dict[str, Any]) -> str:
    remaining = [q for q in questions if not _answer_present(q, answers)]
    if not remaining:
        return ""

    def has_goal(name: str) -> bool:
        vals = answers.get("primary_goal") or []
        if not isinstance(vals, list):
            vals = [vals]
        return name in vals

    priority = []
    if has_goal("Target vs achievement"):
        priority += ["target_column", "main_measures", "important_dimensions", "time_axis"]
    if has_goal("Forecasting") or len(profile.get("time_columns") or []) > 1:
        priority += ["time_axis", "main_measures", "important_dimensions"]
    if has_goal("Top and bottom performers"):
        priority += ["important_dimensions", "main_measures"]
    if has_goal("Contribution / Pareto"):
        priority += ["important_dimensions", "main_measures"]

    priority += [
        "primary_goal",
        "main_measures",
        "target_column",
        "time_axis",
        "important_dimensions",
        "output_mode",
        "business_context",
    ]

    remaining_keys = {q.get("key"): q for q in remaining}
    for key in priority:
        if key in remaining_keys:
            return key
    return remaining[0].get("key", "")


def _ai_next_key(profile: Dict[str, Any], questions: List[Dict[str, Any]], answers: Dict[str, Any], user=None) -> Optional[str]:
    ctx = get_ai_access_context(user, feature="review_next_question", estimated_tokens=700)
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not ctx.get("ai_enabled") or not api_key or anthropic is None:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = AI_NEXT_QUESTION_PROMPT.format(
            profile_json=json.dumps(profile, ensure_ascii=False)[:12000],
            questions_json=json.dumps(questions, ensure_ascii=False)[:12000],
            answers_json=json.dumps(answers, ensure_ascii=False)[:6000],
        )
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=180,
            system="Return strict JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start:end + 1])
            next_key = (data.get("next_key") or "").strip()
            if next_key and any(q.get("key") == next_key for q in questions):
                return next_key
            if next_key == "":
                return ""
    except Exception:
        return None
    return None


def choose_next_question(profile: Dict[str, Any], questions: List[Dict[str, Any]], answers: Dict[str, Any], user=None) -> Tuple[str, str]:
    ai_key = _ai_next_key(profile, questions, answers, user=user)
    if ai_key is not None:
        return ai_key, "ai"
    return _heuristic_next_key(profile, questions, answers), "heuristic"


def build_review_state(profile_obj, answers: Dict[str, Any], user=None) -> Dict[str, Any]:
    questions = profile_obj.question_payload or []
    profile = profile_obj.profile_json or {}
    next_key, source = choose_next_question(profile, questions, answers, user=user)
    current_question = None
    if next_key:
        current_question = next((q for q in questions if q.get("key") == next_key), None)
    total = len(questions)
    answered = sum(1 for q in questions if _answer_present(q, answers))
    return {
        "questions": questions,
        "current_question": current_question,
        "next_key": next_key,
        "selection_source": source,
        "answered_count": answered,
        "total_questions": total,
        "is_complete": total == 0 or answered >= total or not current_question,
        "remaining_questions": [q for q in questions if not _answer_present(q, answers)],
    }
