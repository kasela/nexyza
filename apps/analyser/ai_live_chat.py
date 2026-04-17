from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from django.conf import settings

from .ai_policy import get_ai_access_context
from .ai_screening_session import choose_next_question

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None


CANONICAL_QUESTION_SPECS: Dict[str, Dict[str, Any]] = {
    "primary_goal": {
        "type": "multi_select",
        "max_select": 3,
        "allow_dont_know": False,
        "label": "Dashboard goal",
    },
    "main_measures": {
        "type": "multi_select",
        "max_select": 4,
        "allow_dont_know": False,
        "label": "Priority measures",
    },
    "target_column": {
        "type": "single_select",
        "max_select": 1,
        "allow_dont_know": True,
        "label": "Target mapping",
    },
    "time_axis": {
        "type": "single_select",
        "max_select": 1,
        "allow_dont_know": True,
        "label": "Time story",
    },
    "important_dimensions": {
        "type": "multi_select",
        "max_select": 3,
        "allow_dont_know": False,
        "label": "Breakdowns",
    },
    "output_mode": {
        "type": "single_select",
        "max_select": 1,
        "allow_dont_know": False,
        "label": "Output style",
    },
    "business_context": {
        "type": "text",
        "max_select": 1,
        "allow_dont_know": True,
        "label": "Special focus",
    },
}

DEFAULT_GOALS = [
    "Target vs achievement",
    "Top and bottom performers",
    "Trend over time",
    "Contribution / Pareto",
    "Relationship between variables",
    "Distribution and outliers",
    "Forecasting",
]
DEFAULT_OUTPUT_MODES = [
    "Full analytical dashboard",
    "Executive summary + charts",
    "Forecast focused",
    "Conservative safe output",
]


LIVE_NEXT_TURN_PROMPT = """You are the live dashboard copilot inside a SaaS analytics chat.
You must ask ONLY the next best question, one at a time, based on the dataset profile and the chat so far.
The conversation must feel natural, short, and human. No system wording, no checklist tone, no technical exposition.

Return strict JSON only in this exact shape:
{{
  "done": false,
  "question": {{
    "key": "one_of_primary_goal_main_measures_target_column_time_axis_important_dimensions_output_mode_business_context",
    "type": "single_select|multi_select|text",
    "prompt": "short natural question",
    "helper": "optional short helper",
    "choices": [{{"value": "exact value", "label": "short label", "emoji": "optional emoji"}}],
    "max_select": 3,
    "allow_skip": true,
    "allow_dont_know": true,
    "placeholder": "optional"
  }}
}}
OR if enough context exists:
{{
  "done": true,
  "message": "short natural ready message"
}}

Rules:
- Ask one question only.
- Use the provided next_key as the subject area. Do not invent a different key.
- Keep prompts under 22 words.
- Use actual dataset field names whenever relevant.
- Choice values must be exact field names or exact allowed option values.
- Keep 2 to 6 choices only.
- Multi-select choices should be highly relevant, not exhaustive.
- Avoid phrases like "I detected", "current focus", "analysis type", "profile", "prioritise chart planning".
- Sound like a sharp human analyst in chat.
- If key is business_context, prefer text unless a short select is clearly better.

ALLOWED KEY SPECS:
{specs_json}

PROFILE:
{profile_json}

CURRENT ANSWERS:
{answers_json}

CHAT HISTORY:
{history_json}

NEXT KEY TO ASK:
{next_key}
"""


LIVE_INTRO_PROMPT = """You are greeting a user inside a premium analytics SaaS chat.
Write one very short opening message after reviewing their uploaded dataset.
Rules:
- 8 to 18 words.
- Friendly, confident, natural.
- No mention of rows, columns, profiling, schema, readiness, workflow, or setup.
- No bullet points.
- It should feel like the start of a real chat.

PROFILE:
{profile_json}
"""


def _safe_history(turns) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for turn in list(turns)[-8:]:
        text = (turn.answer_label or turn.message or "").strip()
        if not text:
            continue
        out.append({"role": turn.role, "kind": turn.kind, "text": text[:300]})
    return out


def _call_json(prompt: str, system: str, max_tokens: int = 500) -> Optional[Dict[str, Any]]:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key or anthropic is None:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    except Exception:
        return None
    return None


def generate_intro_message(profile: Dict[str, Any], user=None) -> str:
    ctx = get_ai_access_context(user, feature="review_live_intro", estimated_tokens=250)
    if ctx.get("ai_enabled"):
        prompt = LIVE_INTRO_PROMPT.format(profile_json=json.dumps(profile, ensure_ascii=False)[:12000])
        data = _call_json(
            prompt=f'{{"message_request": {json.dumps(prompt, ensure_ascii=False)} }}',
            system="Return strict JSON only in the form {\"message\":\"...\"}.",
            max_tokens=120,
        )
        if isinstance(data, dict) and str(data.get("message", "")).strip():
            return str(data["message"]).strip()
    return "Hey — I’ve looked through your file. Let’s shape the right dashboard."


def _fallback_question(profile: Dict[str, Any], next_key: str) -> Dict[str, Any]:
    measures = profile.get("measures") or []
    dims = profile.get("dimensions") or []
    times = profile.get("time_columns") or []
    targets = profile.get("target_columns") or []

    if next_key == "primary_goal":
        return {
            "key": next_key,
            "type": "multi_select",
            "prompt": "What do you want this dashboard to help you see first?",
            "helper": "Pick the outcomes that matter most.",
            "choices": [{"value": x, "label": x} for x in DEFAULT_GOALS[:5]],
            "max_select": 3,
            "allow_skip": True,
            "allow_dont_know": False,
        }
    if next_key == "main_measures":
        choices = measures[:6] or ["Value"]
        return {
            "key": next_key,
            "type": "multi_select",
            "prompt": "Which numbers should I treat as the main KPIs?",
            "helper": "Choose the measures that matter most.",
            "choices": [{"value": x, "label": x} for x in choices],
            "max_select": 4,
            "allow_skip": True,
            "allow_dont_know": False,
        }
    if next_key == "target_column":
        choices = (targets[:5] or []) + ["None"]
        return {
            "key": next_key,
            "type": "single_select",
            "prompt": "Should I compare performance against a target or benchmark?",
            "helper": "Choose the best target field, or None.",
            "choices": [{"value": x, "label": x} for x in choices],
            "max_select": 1,
            "allow_skip": True,
            "allow_dont_know": True,
        }
    if next_key == "time_axis":
        choices = (times[:5] or []) + ["None"]
        return {
            "key": next_key,
            "type": "single_select",
            "prompt": "Should the dashboard show a trend over time?",
            "helper": "Pick the best time field, or None.",
            "choices": [{"value": x, "label": x} for x in choices],
            "max_select": 1,
            "allow_skip": True,
            "allow_dont_know": True,
        }
    if next_key == "important_dimensions":
        choices = dims[:6] or ["Category"]
        return {
            "key": next_key,
            "type": "multi_select",
            "prompt": "Which breakdowns should I use most in the dashboard?",
            "helper": "Pick the groups you care about most.",
            "choices": [{"value": x, "label": x} for x in choices],
            "max_select": 3,
            "allow_skip": True,
            "allow_dont_know": False,
        }
    if next_key == "output_mode":
        return {
            "key": next_key,
            "type": "single_select",
            "prompt": "What kind of dashboard do you want me to build?",
            "helper": "Choose the output style.",
            "choices": [{"value": x, "label": x} for x in DEFAULT_OUTPUT_MODES[:4]],
            "max_select": 1,
            "allow_skip": True,
            "allow_dont_know": False,
        }
    return {
        "key": "business_context",
        "type": "text",
        "prompt": "Anything specific you want me to highlight?",
        "helper": "For example: underperformers, gaps, or key contributors.",
        "allow_skip": True,
        "allow_dont_know": True,
        "placeholder": "Type what matters most",
    }


def _sanitize_live_question(data: Dict[str, Any], profile: Dict[str, Any], next_key: str) -> Dict[str, Any]:
    question = (data or {}).get("question") if isinstance(data, dict) else None
    if not isinstance(question, dict):
        return _fallback_question(profile, next_key)

    spec = CANONICAL_QUESTION_SPECS.get(next_key, {})
    q_type = question.get("type") or spec.get("type") or "text"
    if q_type not in {"single_select", "multi_select", "text"}:
        q_type = spec.get("type") or "text"

    cleaned: Dict[str, Any] = {
        "key": next_key,
        "type": q_type,
        "prompt": str(question.get("prompt") or _fallback_question(profile, next_key).get("prompt") or "").strip()[:180],
        "helper": str(question.get("helper") or "").strip()[:220],
        "allow_skip": True,
        "allow_dont_know": bool(question.get("allow_dont_know", spec.get("allow_dont_know", False))),
        "max_select": int(question.get("max_select") or spec.get("max_select") or 1),
        "placeholder": str(question.get("placeholder") or "").strip()[:120],
    }

    if q_type in {"single_select", "multi_select"}:
        raw_choices = question.get("choices") or []
        choices: List[Dict[str, str]] = []
        seen = set()
        for item in raw_choices[:8]:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            label = str(item.get("label") or value).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            obj = {"value": value, "label": label[:60]}
            emoji = str(item.get("emoji") or "").strip()
            if emoji:
                obj["emoji"] = emoji[:4]
            choices.append(obj)
        if not choices:
            return _fallback_question(profile, next_key)
        cleaned["choices"] = choices[:6]

    return cleaned


def generate_live_next_turn(session, profile_obj, answers: Dict[str, Any], user=None) -> Dict[str, Any]:
    profile = profile_obj.profile_json or {}
    next_key, fallback_source = choose_next_question(profile, profile_obj.question_payload or [], answers, user=user)
    if not next_key:
        return {
            "done": True,
            "message": "Perfect — I have enough. I’ll build the dashboard around that.",
            "source": fallback_source,
        }

    ctx = get_ai_access_context(user, feature="review_live_turn", estimated_tokens=1200)
    if ctx.get("ai_enabled"):
        prompt = LIVE_NEXT_TURN_PROMPT.format(
            specs_json=json.dumps(CANONICAL_QUESTION_SPECS, ensure_ascii=False),
            profile_json=json.dumps(profile, ensure_ascii=False)[:12000],
            answers_json=json.dumps(answers, ensure_ascii=False)[:6000],
            history_json=json.dumps(_safe_history(session.turns.all()), ensure_ascii=False)[:6000],
            next_key=next_key,
        )
        data = _call_json(prompt=prompt, system="Return strict JSON only.", max_tokens=600)
        if isinstance(data, dict):
            if data.get("done") is True:
                return {
                    "done": True,
                    "message": str(data.get("message") or "Perfect — I have enough. I’ll build the dashboard around that.").strip()[:220],
                    "source": "ai_live",
                }
            return {
                "done": False,
                "question": _sanitize_live_question(data, profile, next_key),
                "source": "ai_live",
            }

    return {
        "done": False,
        "question": _fallback_question(profile, next_key),
        "source": f"fallback_{fallback_source}",
    }
