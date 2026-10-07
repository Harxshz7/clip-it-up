import hashlib
import json
import time
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from clip_shared.config import get_settings
from clip_shared.prompts.clip_score_v1 import (
    ClipScoreFlags,
    Pass1BatchResponse,
    Pass1CoarseScore,
    Pass2CandidateScore,
)

logger = structlog.get_logger()
settings = get_settings()

T = TypeVar("T", bound=BaseModel)

# In-memory / process-level response cache (hash -> (data, in_tokens, out_tokens))
_LLM_RESPONSE_CACHE: dict[str, tuple[dict[str, Any], int, int]] = {}


def compute_cache_key(prompt_version: str, model: str, content: str) -> str:
    h = hashlib.sha256()
    h.update(prompt_version.encode("utf-8"))
    h.update(b":")
    h.update(model.encode("utf-8"))
    h.update(b":")
    h.update(content.strip().encode("utf-8"))
    return h.hexdigest()


class LLMClient:
    """
    Structured LLM client wrapper for Claude / Anthropic API with JSON validation,
    deterministic caching, token counting, cost tracking, and offline mock fallback.
    """

    def __init__(
        self,
        api_key: str | None = None,
        backend: str | None = None,
        cache_enabled: bool = True,
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.backend = backend or settings.LLM_SCORER_BACKEND
        self.cache_enabled = cache_enabled

        # Model pricing (USD per million tokens)
        self.pricing = {
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
            "mock": {"input": 0.0, "output": 0.0},
        }

    def calculate_cost_inr(self, model: str, in_tokens: int, out_tokens: int) -> float:
        rates = self.pricing.get(model, {"input": 1.0, "output": 5.0})
        cost_usd = (in_tokens / 1_000_000.0) * rates["input"] + (out_tokens / 1_000_000.0) * rates["output"]
        return cost_usd * settings.USD_TO_INR_RATE

    def call_structured(
        self,
        prompt: str,
        model: str,
        response_schema: type[T],
        prompt_version: str = "v1",
        system_prompt: str | None = None,
        max_retries: int = 2,
    ) -> tuple[T, int, int, float, bool]:
        """
        Execute structured LLM call with Pydantic schema validation and response caching.
        Returns: (parsed_model, input_tokens, output_tokens, cost_inr, is_cache_hit)
        """
        cache_key = compute_cache_key(prompt_version, model, prompt)
        if self.cache_enabled and cache_key in _LLM_RESPONSE_CACHE:
            cached_data, in_tok, out_tok = _LLM_RESPONSE_CACHE[cache_key]
            try:
                parsed = response_schema.model_validate(cached_data)
                cost = self.calculate_cost_inr(model, in_tok, out_tok)
                return parsed, in_tok, out_tok, cost, True
            except ValidationError:
                pass

        if self.backend == "mock" or not self.api_key:
            parsed, in_tok, out_tok = self._generate_mock_response(prompt, response_schema)
            cost = self.calculate_cost_inr(model, in_tok, out_tok)
            if self.cache_enabled:
                _LLM_RESPONSE_CACHE[cache_key] = (parsed.model_dump(), in_tok, out_tok)
            return parsed, in_tok, out_tok, cost, False

        # Live Anthropic API Call
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)

        for attempt in range(max_retries):
            try:
                # Use JSON output schema instruction
                tool_schema = {
                    "name": "submit_score",
                    "description": "Submit structured score evaluation",
                    "input_schema": response_schema.model_json_schema(),
                }

                messages = [{"role": "user", "content": prompt}]
                response = client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=system_prompt or "You are a precise video virality scoring system. Always output accurate structured JSON.",
                    tools=[tool_schema],
                    tool_choice={"type": "tool", "name": "submit_score"},
                    messages=messages,
                    temperature=0.2,
                )

                in_tok = response.usage.input_tokens
                out_tok = response.usage.output_tokens
                cost = self.calculate_cost_inr(model, in_tok, out_tok)

                # Extract tool call input
                tool_call = next((b for b in response.content if b.type == "tool_use"), None)
                if tool_call and tool_call.input:
                    parsed = response_schema.model_validate(tool_call.input)
                    if self.cache_enabled:
                        _LLM_RESPONSE_CACHE[cache_key] = (parsed.model_dump(), in_tok, out_tok)
                    return parsed, in_tok, out_tok, cost, False

                # Fallback check for raw text JSON
                text_content = "".join(b.text for b in response.content if hasattr(b, "text"))
                raw_json = json.loads(text_content)
                parsed = response_schema.model_validate(raw_json)
                if self.cache_enabled:
                    _LLM_RESPONSE_CACHE[cache_key] = (parsed.model_dump(), in_tok, out_tok)
                return parsed, in_tok, out_tok, cost, False

            except (ValidationError, json.JSONDecodeError, anthropic.APIError) as ex:
                logger.warning("llm_call_attempt_failed", attempt=attempt, error=str(ex))
                if attempt == max_retries - 1:
                    logger.error("llm_call_fallback_to_mock", error=str(ex))
                    parsed, in_tok, out_tok = self._generate_mock_response(prompt, response_schema)
                    cost = self.calculate_cost_inr(model, in_tok, out_tok)
                    return parsed, in_tok, out_tok, cost, False
                time.sleep(1.0 * (attempt + 1))

        # Ultimate fallback
        parsed, in_tok, out_tok = self._generate_mock_response(prompt, response_schema)
        cost = self.calculate_cost_inr(model, in_tok, out_tok)
        return parsed, in_tok, out_tok, cost, False

    def _generate_mock_response(self, prompt: str, schema: type[T]) -> tuple[T, int, int]:
        """Generate deterministic, realistic mock response based on prompt text."""
        in_tok = len(prompt.split()) * 2
        out_tok = 150

        if schema == Pass1BatchResponse:
            # Extract candidate ids like [cand_0]
            import re
            ids = re.findall(r"\[([a-zA-Z0-9_\-]+)\]", prompt)
            if not ids:
                ids = ["cand_0", "cand_1", "cand_2"]

            scores = []
            for i, cid in enumerate(ids):
                # Deterministic scoring based on hash
                h_val = int(hashlib.md5(cid.encode("utf-8")).hexdigest()[:4], 16)
                score = round(4.0 + (h_val % 60) / 10.0, 1)  # 4.0 to 10.0
                scores.append(Pass1CoarseScore(
                    id=cid,
                    coarse_score=score,
                    reason=f"Strong hook and clear narrative arc in segment {i+1}.",
                ))
            return Pass1BatchResponse(scores=scores), in_tok, out_tok

        elif schema == Pass2CandidateScore:
            import re
            id_match = re.search(r"ID:\s*([a-zA-Z0-9_\-]+)", prompt)
            candidate_id = id_match.group(1) if id_match else "cand_0"

            start_m = re.search(r"Range:\s*(\d+)ms\s*to\s*(\d+)ms", prompt)
            start_ms = int(start_m.group(1)) if start_m else 0
            end_ms = int(start_m.group(2)) if start_m else 30000

            # Extract first sentence for hook
            lines = prompt.split('Transcript:\n"')
            trans_text = lines[1].split('"\n')[0] if len(lines) > 1 else "Why do most startups fail in their first year?"
            first_sentence = trans_text.split(".")[0].split("?")[0] + ("?" if "?" in trans_text else ".")

            h_val = int(hashlib.md5(trans_text.encode("utf-8")).hexdigest()[:4], 16)
            base_score = 0.60 + (h_val % 35) / 100.0  # 0.60 to 0.95

            # Refined trims
            suggested_start = start_ms
            suggested_end = max(suggested_start + 15000, end_ms - 500)

            score_obj = Pass2CandidateScore(
                id=candidate_id,
                hook=round(min(1.0, base_score + 0.05), 2),
                emotion=round(min(1.0, base_score - 0.05), 2),
                coherence=round(min(1.0, base_score + 0.08), 2),
                payoff=round(min(1.0, base_score), 2),
                novelty=round(min(1.0, base_score - 0.02), 2),
                best_hook_text=first_sentence.strip()[:100],
                suggested_start_ms=suggested_start,
                suggested_end_ms=suggested_end,
                title="The Single Biggest Mistake Founders Make",
                reason="Opens with an immediate curiosity gap and concludes with a definitive, actionable insight.",
                flags=ClipScoreFlags(needs_context=False, off_topic=False, profanity=False, sensitive=False),
            )
            return score_obj, in_tok, out_tok

        raise ValueError(f"Unsupported mock response schema: {schema}")
