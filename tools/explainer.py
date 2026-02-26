"""Natural-language explanation generator with compliance guardrails."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

from config.settings import settings
from schemas.response_schemas import Prediction
from tools.error_handler import ValidationError


def _top_features(feature_importance: Dict[str, float], k: int = 3) -> List[Tuple[str, float]]:
    return sorted(feature_importance.items(), key=lambda item: item[1], reverse=True)[:k]


def _validate_compliance(text: str) -> None:
    """Validate that explanation doesn't contain forbidden financial advice terms."""
    import re
    
    lowered = text.lower()
    forbidden = []
    
    # Check for forbidden words as whole words only (not substrings)
    for word in settings.forbidden_words:
        # Use word boundaries to match whole words only
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, lowered):
            forbidden.append(word)
    
    if forbidden:
        raise ValidationError(
            f"Generated explanation contains restricted terminology: {', '.join(forbidden)}",
            failed_step="EXPLAIN_RESULT",
        )


from tools.llm_client import llm_client

def generate_explanation(
    ticker: str,
    exchange: str,
    target_date: date,
    prediction: Prediction,
    research_data: Dict[str, Any] | None = None,
) -> str:
    """Create educational explanation including top features, interval, and research context."""
    top3 = _top_features(prediction.feature_importance, 3)
    feature_text = ", ".join([f"{name} ({score:.3f})" for name, score in top3]) or "price trend features"

    # Integrate research if available
    research_context = ""
    if research_data and research_data.get("synthesis"):
        research_context = f"\nFundamental Context: {research_data.get('synthesis')}"
        if research_data.get("catalysts"):
            cats = [c["catalyst"] if isinstance(c, dict) else str(c) for c in research_data.get("catalysts", [])[:3]]
            research_context += f"\nKey Catalysts: {', '.join(cats)}"

    # Try LLM for professional narrative
    system_prompt = "You are a professional quantitative research assistant. Provide concise, objective investment research analysis."
    user_prompt = f"""Generate a professional technical analysis summary for {ticker} ({exchange}).
Target Date: {target_date.isoformat()}
Predicted Price: {prediction.point_estimate:.2f}
80% Confidence Interval: [{prediction.lower_bound:.2f}, {prediction.upper_bound:.2f}]
Top Model Features: {feature_text}
{research_context}

Guidelines:
- Synthesize both the technical indicators and the fundamental research context.
- Explain how catalysts might be impacting the price target.
- Maintain a neutral, educational tone.
- Do NOT give financial advice.
- Keep it under 110 words.
"""
    
    explanation = ""
    try:
        explanation = llm_client.chat_completion(system_prompt, user_prompt, temperature=0.3, max_tokens=150)
    except Exception:
        explanation = ""

    # Fallback to rule-based if LLM fails or is empty
    if not explanation:
        explanation = (
            f"For {ticker} on {exchange}, the projected close for {target_date.isoformat()} is "
            f"{prediction.point_estimate:.2f}, with an 80% interval of "
            f"{prediction.lower_bound:.2f} to {prediction.upper_bound:.2f}. "
            f"The strongest model signals were: {feature_text}. "
            f"Outcome uncertainty can be significant because market behavior changes quickly. "
        )

    # Ensure disclaimer is always present
    if settings.disclaimer not in explanation:
        explanation += f"\n\n{settings.disclaimer}"

    _validate_compliance(explanation)
    return explanation

