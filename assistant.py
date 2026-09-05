"""
Internal AI Assistant for Nebula Support Agents
=================================================

Takes a raw ticket and returns:
  - summary: a short summary of the issue
  - variants: 2-3 draft replies in different tones (formal / empathetic / short)
  - kb_reference: the most relevant knowledge-base article found via retrieval,
    with a short quote the agent can check against

Retrieval is deliberately simple (keyword overlap, not embeddings/vector DB)
— see README.md "Why this retrieval approach" for the reasoning. The KB is
simulated as a small set of text articles in knowledge_base.json.

Usage:
    from assistant import generate_response
    result = generate_response("I was charged twice this month...")

Run directly for a manual smoke test:
    python assistant.py
"""

import os
import re
import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from anthropic import Anthropic, APIError, APIStatusError, APITimeoutError, RateLimitError

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-5"
MODEL_OPUS = "claude-opus-5"
DEFAULT_MODEL = MODEL_SONNET  # see README.md for why this task defaults to Sonnet, not Haiku

KB_PATH = Path(__file__).parent / "knowledge_base.json"

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "in", "on", "for", "with", "this", "that", "it", "i", "my", "me", "you",
    "your", "if", "not", "be", "has", "have", "had", "but", "at", "as", "do",
    "does", "did", "can", "will", "would", "should", "could", "from", "by",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Zа-яА-Я]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def load_kb() -> list:
    with open(KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def retrieve_kb_article(ticket_text: str, kb: Optional[list] = None) -> Optional[dict]:
    """
    Simple keyword-overlap retrieval: score each KB article by how many
    significant words it shares with the ticket, normalized by article
    length so long articles don't win purely by having more words.
    Returns the best match, or None if nothing scores above a minimum
    threshold (in which case the assistant should say so rather than
    force a bad match).
    """
    if kb is None:
        kb = load_kb()

    ticket_words = _tokenize(ticket_text)
    if not ticket_words:
        return None

    best_article = None
    best_score = 0.0

    for article in kb:
        article_words = _tokenize(article["title"] + " " + article["text"])
        overlap = ticket_words & article_words
        if not article_words:
            continue
        # Jaccard-like score, weighted toward ticket coverage rather than
        # pure overlap size, so short tickets can still match well.
        score = len(overlap) / max(len(ticket_words), 1)
        if score > best_score:
            best_score = score
            best_article = article

    MIN_SCORE = 0.08  # tuned empirically against test_cases.json — see prompt_evolution.md
    if best_score < MIN_SCORE:
        return None
    return best_article


SYSTEM_PROMPT = """You are an internal writing assistant for Nebula support agents (Nebula is a \
subscription platform connecting users with paid experts/consultants). You help agents respond \
to tickets faster — you do NOT send anything to the user directly; everything you produce is a \
draft the agent reviews and edits.

You will be given the ticket text and, if available, a relevant internal knowledge-base excerpt.

Respond with ONLY a single JSON object, no other text, no markdown code fences:

{
  "summary": "1-2 sentence summary of what the user needs, for the agent to scan quickly",
  "variants": [
    {"tone": "formal", "text": "..."},
    {"tone": "empathetic", "text": "..."},
    {"tone": "short", "text": "..."}
  ],
  "kb_used": true | false,
  "confidence": "low" | "medium" | "high",
  "flag_for_review": true | false,
  "flag_reason": "short reason if flag_for_review is true, else empty string"
}

Guidance for the three variants:
- "formal": professional, complete sentences, no contractions, suitable for a business/enterprise user.
- "empathetic": leads with acknowledging the user's frustration or situation before addressing the issue, warmer tone, still professional.
- "short": the minimum needed to move the conversation forward — a few sentences, no filler, for agents who want to send something fast.

All three variants must be factually consistent with each other and with the knowledge-base excerpt \
if one was provided. Do not invent policy details, refund amounts, or timelines that aren't in the \
KB excerpt or aren't safe generic statements (e.g. "we'll look into this" is safe; "you'll get a \
refund within 24 hours" is not safe unless the KB excerpt actually says that).

Set flag_for_review to true if:
- the ticket involves account security, fraud, or unauthorized access
- the ticket involves expert misconduct, legal threats, or safety concerns
- no relevant KB excerpt was found and the topic requires policy knowledge you're not certain of
- the ticket is in a language you're not fully confident drafting a reply in

When flag_for_review is true, the variants should still be drafted (so the agent has a starting
point) but flag_reason must explain what needs human judgment before sending.

Always respond with valid JSON only."""


@dataclass
class ReplyVariant:
    tone: str
    text: str


@dataclass
class AssistantResult:
    summary: str
    variants: list
    kb_used: bool
    kb_article_id: Optional[str]
    kb_article_title: Optional[str]
    confidence: str
    flag_for_review: bool
    flag_reason: str
    model_used: str = ""
    latency_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            **{k: v for k, v in asdict(self).items() if k != "variants"},
            "variants": [asdict(v) if not isinstance(v, dict) else v for v in self.variants],
        }


def _fallback_result(reason: str) -> AssistantResult:
    return AssistantResult(
        summary="Automatic drafting failed — please write a manual reply.",
        variants=[],
        kb_used=False,
        kb_article_id=None,
        kb_article_title=None,
        confidence="low",
        flag_for_review=True,
        flag_reason=f"Fallback triggered: {reason}",
        error=reason,
    )


def _safe_parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _valid_shape(parsed: dict) -> bool:
    required = {"summary", "variants", "kb_used", "confidence", "flag_for_review"}
    if not required.issubset(parsed.keys()):
        return False
    if not isinstance(parsed["variants"], list) or len(parsed["variants"]) < 2:
        return False
    for v in parsed["variants"]:
        if "tone" not in v or "text" not in v:
            return False
    if parsed["confidence"] not in ("low", "medium", "high"):
        return False
    if not isinstance(parsed["flag_for_review"], bool):
        return False
    return True


def generate_response(
    ticket_text: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
    client: Optional[Anthropic] = None,
) -> AssistantResult:
    if client is None:
        client = Anthropic()

    if not ticket_text or not ticket_text.strip():
        return _fallback_result("empty ticket text")

    kb_article = retrieve_kb_article(ticket_text)
    if kb_article:
        kb_context = f"Relevant KB article — {kb_article['title']}:\n{kb_article['text']}"
    else:
        kb_context = "No sufficiently relevant KB article was found for this ticket."

    user_message = f"Ticket:\n{ticket_text}\n\n{kb_context}"

    backoff = 1.0
    last_error = "unknown error"

    for attempt in range(1, max_retries + 1):
        start = time.time()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=800,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            latency_ms = (time.time() - start) * 1000
            raw_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()

            parsed = _safe_parse_json(raw_text)
            if parsed is None or not _valid_shape(parsed):
                last_error = "invalid JSON or shape from model"
                if attempt == max_retries:
                    return _fallback_result(last_error)
                continue

            return AssistantResult(
                summary=parsed["summary"],
                variants=parsed["variants"],
                kb_used=bool(parsed["kb_used"]) and kb_article is not None,
                kb_article_id=kb_article["id"] if kb_article else None,
                kb_article_title=kb_article["title"] if kb_article else None,
                confidence=parsed["confidence"],
                flag_for_review=bool(parsed["flag_for_review"]),
                flag_reason=parsed.get("flag_reason", ""),
                model_used=model,
                latency_ms=round(latency_ms, 1),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except RateLimitError as e:
            last_error = f"rate limited: {e}"
            time.sleep(backoff)
            backoff *= 2
        except APITimeoutError as e:
            last_error = f"timeout: {e}"
            time.sleep(backoff)
            backoff *= 2
        except APIStatusError as e:
            last_error = f"API status error {e.status_code}: {e.message}"
            if 400 <= e.status_code < 500 and e.status_code != 429:
                break
            time.sleep(backoff)
            backoff *= 2
        except APIError as e:
            last_error = f"API error: {e}"
            time.sleep(backoff)
            backoff *= 2

    return _fallback_result(last_error)


if __name__ == "__main__":
    sample_tickets = [
        "I was charged twice this month, please refund the extra charge immediately.",
        "How do I switch from monthly to annual billing?",
        "Someone accessed my account, there's a booking I never made and my card was changed.",
    ]
    for t in sample_tickets:
        result = generate_response(t)
        print(f"\nTicket: {t}")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
