"""AI Referee, part 2: Socratic feedback.

The sandbox decides pass/fail; the AI never grades and never hands out solutions. When
a submission fails, Claude writes a short hint in the student's language that points at
the misconception. Without an API key we fall back to a deterministic, rule-based hint,
so the platform still works offline.
"""
import json
import logging

from .. import config
from ..models import Challenge

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Tempa's coding referee for university students in Malaysia.
A student's Python submission failed some automated tests. Write ONE short hint
(max 70 words) that helps them find the bug themselves.
Never write corrected code, never reveal the full algorithm, and never mention hidden test inputs.
Point at the specific misconception visible in their code. Be warm but direct.
Reply only in {language}."""

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def rule_based_hint(result: dict, lang: str) -> str:
    ms = lang == "ms"
    if result.get("error"):
        err = result["error"]
        if err == "timeout":
            return ("Kod anda mengambil masa terlalu lama. Semak gelung yang mungkin tidak berhenti."
                    if ms else "Your code took too long. Look for a loop that never terminates.")
        if err.startswith(("import_not_allowed", "name_not_allowed", "dunder_access_not_allowed")):
            return (f"Kod ini menggunakan ciri yang tidak dibenarkan dalam referee ({err}). Gunakan Python asas sahaja."
                    if ms else f"This uses a feature the referee doesn't allow ({err}). Stick to plain Python.")
        return (f"Kod anda gagal dijalankan: {err}. Baiki ralat ini dahulu."
                if ms else f"Your code failed to run: {err}. Fix this error first.")
    for c in result.get("cases", []):
        if c["ok"]:
            continue
        if not c["hidden"]:
            if c.get("error"):
                return (f"Untuk input {c['args']}, fungsi anda menimbulkan {c['error']}."
                        if ms else f"For input {c['args']}, your function raised {c['error']}.")
            return (f"Untuk input {c['args']}, anda pulangkan {c['got']!r} tetapi dijangka {c['expected']!r}."
                    if ms else f"For input {c['args']}, you returned {c['got']!r} but {c['expected']!r} was expected.")
    return ("Ujian yang kelihatan lulus, tetapi kes tersembunyi gagal. Fikirkan kes tepi: input kosong, nombor negatif, huruf besar/kecil."
            if ms else "Visible tests pass but hidden edge cases fail. Think about empty input, negative numbers and letter case.")


def hint(challenge: Challenge, code: str, result: dict, lang: str = "en") -> dict:
    """Return {"text", "source"} where source is "ai" or "rules"."""
    fallback = {"text": rule_based_hint(result, lang), "source": "rules"}
    if not config.AI_COACH_ENABLED:
        return fallback

    visible_failures = [c for c in result.get("cases", []) if not c["ok"] and not c["hidden"]]
    hidden_failed = sum(1 for c in result.get("cases", []) if not c["ok"] and c["hidden"])
    user_msg = (
        f"Task:\n{challenge.prompt_en}\n\nStudent code:\n```python\n{code}\n```\n\n"
        f"Runtime error: {result.get('error') or 'none'}\n"
        f"Failing visible tests: {json.dumps(visible_failures, default=str)}\n"
        f"Number of failing hidden tests: {hidden_failed}"
    )
    try:
        import anthropic
        response = _get_client().beta.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT.format(language="Bahasa Melayu" if lang == "ms" else "English"),
            messages=[{"role": "user", "content": user_msg}],
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as e:
        log.warning("AI coach unavailable, using rule-based hint: %s", e)
        return fallback

    if response.stop_reason == "refusal":
        return fallback
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return {"text": text, "source": "ai"} if text else fallback
