from __future__ import annotations

from typing import Any, Dict
from django.conf import settings


def get_ai_access_context(user=None, feature: str = "analysis", estimated_tokens: int = 0) -> Dict[str, Any]:
    api_key = bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
    ctx = {
        "feature": feature,
        "api_available": api_key,
        "ai_enabled": False,
        "source": "manual",
        "reason": "",
        "upgrade_required": False,
        "purchase_tokens_recommended": False,
        "remaining_tokens": None,
        "estimated_tokens": estimated_tokens or 0,
        "message": "",
    }
    if not api_key:
        ctx["reason"] = "Anthropic API key is not configured."
        ctx["message"] = "AI is unavailable right now, so Nexyza will use the manual analysis engine."
        return ctx
    if user is None or not getattr(user, 'is_authenticated', False):
        ctx["reason"] = "No authenticated user."
        ctx["message"] = "Sign in to use AI-assisted analysis."
        return ctx
    try:
        from apps.billing.models import TokenUsage
        ok, reason = TokenUsage.can_use_ai(user)
        remaining = TokenUsage.budget_remaining(user)
        ctx["remaining_tokens"] = remaining
        if ok:
            ctx["ai_enabled"] = True
            ctx["source"] = "ai"
            ctx["reason"] = "ok"
            ctx["message"] = "AI-assisted analysis is available for this dataset."
            return ctx
        ctx["reason"] = reason
        sub = getattr(user, 'subscription', None)
        if not sub or not getattr(sub, 'can_use_ai', False):
            ctx["upgrade_required"] = True
            ctx["message"] = "Upgrade to Plus or Pro to unlock AI-guided dataset screening and better chart planning."
        else:
            ctx["purchase_tokens_recommended"] = True
            ctx["message"] = "Your AI token budget is exhausted. Buy additional tokens or wait for the monthly reset to restore AI analysis."
        return ctx
    except Exception:
        ctx["reason"] = "Subscription or token usage could not be checked."
        ctx["message"] = "AI access could not be verified, so Nexyza will use the manual analysis engine."
        return ctx
