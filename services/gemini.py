import os
import requests
from typing import Dict, Any, Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_ENDPOINT = os.getenv("GEMINI_ENDPOINT") or "https://generativelanguage.googleapis.com/v1beta2/models/text-bison-001:generate"


def _call_gemini(prompt: str, timeout: int = 10) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        body = {
            "prompt": {"text": prompt},
            "temperature": 0.2,
            "maxOutputTokens": 512
        }
        params = {"key": GEMINI_API_KEY}
        resp = requests.post(GEMINI_ENDPOINT, params=params, json=body, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # attempt to extract generated text from several possible shapes
        if isinstance(data, dict):
            # common field: 'candidates' -> [{'content': '...'}]
            cands = data.get('candidates') or data.get('outputs') or []
            if isinstance(cands, list) and len(cands) > 0:
                first = cands[0]
                if isinstance(first, dict):
                    return first.get('content') or first.get('text') or None
            # fallback to 'output' or direct 'text'
            if 'output' in data and isinstance(data['output'], str):
                return data['output']
            if 'text' in data and isinstance(data['text'], str):
                return data['text']
        return None
    except Exception:
        return None


def compose_explanation(needs: Dict[str, Any], listing: Optional[Dict], suggested_budgets: Dict[str, float], details: Dict[str, Any]) -> str:
    # Build a short prompt asking Gemini to explain the recommendation.
    prompt = (
        "You are a helpful financial assistant. Given the family's needs and a housing listing, "
        "write a brief, user-facing explanation describing why this listing meets the minimum requirements, "
        "and list proposed per-category budget adjustments in one short paragraph.\n\n"
        f"Family details: {details}.\n"
        f"Minimum needs: {needs}.\n"
        f"Selected listing: {listing}.\n"
        f"Suggested budgets: {suggested_budgets}.\n"
        "Keep it concise and actionable."
    )
    gen = _call_gemini(prompt)
    if gen:
        return gen
    # Fallback simple explanation
    expl = "Recommendation:\n"
    if listing:
        expl += f"Found listing at {listing.get('address')} for ${listing.get('price')}. "
    expl += f"Minimum needs: {needs.get('beds')} beds, {needs.get('baths')} baths, {needs.get('sqft')} sqft.\n"
    expl += "Suggested budget updates: "
    parts = []
    for k, v in suggested_budgets.items():
        parts.append(f"{k}: ${v:.2f}")
    expl += ", ".join(parts)
    return expl
