"""Gemini client: cached, quota-tracked, retried, reproducible.

• Same prompt + model + settings → answered from cache (no quota used).
• Every prompt and response is saved in the project's prompts/ folder
  (proof of originality + reproducibility).
• On 429 (rate limit) it waits and retries; if a model's daily quota is
  used up it moves on to the next model in config.gemini.models.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .cache import DiskCache
from .config import Config, get_secret
from .errors import QuotaExceededError, StudioError
from .hashing import hash_obj
from .log import get_logger
from .quota import QuotaLedger
from .retry import with_retries

log = get_logger("llm")

# Words that must never appear in prompts (we never imitate existing IP).
# Stage outputs add brand terms found during research to this list at runtime.
BASE_BANNED_PROMPT_TERMS: set[str] = set()


def _status_code(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    m = re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
    return int(m.group(1)) if m else None


def _is_daily_quota(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "per day" in text or "perday" in text or "daily" in text


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating ```json fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
        if start >= 0:
            return json.loads(text[start:])
        raise


class GeminiClient:
    def __init__(self, cfg: Config, cache_root: Path, quota: QuotaLedger, prompts_dir: Path | None = None):
        self.cfg = cfg
        self.models: list[str] = list(cfg.get_path("gemini.models", ["gemini-2.5-flash"]))
        self.cache = DiskCache(cache_root, "gemini")
        self.quota = quota
        self.prompts_dir = prompts_dir
        self._client = None

    def _sdk(self):
        if self._client is None:
            api_key = get_secret("GEMINI_API_KEY")
            try:
                from google import genai
            except ModuleNotFoundError as exc:
                raise StudioError("The Gemini package (google-genai) is not installed.",
                                  fix="pip install -r requirements.txt") from exc
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _check_banned(self, prompt: str, banned: set[str]) -> None:
        lowered = prompt.lower()
        hits = sorted(t for t in banned if t and re.search(rf"\b{re.escape(t.lower())}\b", lowered))
        if hits:
            raise StudioError(
                f"Prompt contains protected names: {', '.join(hits)}",
                fix="This is a safety stop: prompts must never name existing characters, "
                "shows, channels or artists. Remove those words.",
            )

    def generate(self, prompt: str, *, purpose: str, temperature: float | None = None,
                 seed: int | None = None, json_mode: bool = True,
                 banned_terms: set[str] | None = None) -> Any:
        self._check_banned(prompt, BASE_BANNED_PROMPT_TERMS | (banned_terms or set()))
        temperature = self.cfg.get_path("gemini.temperature", 0.7) if temperature is None else temperature
        seed = self.cfg.get_path("project.seed", 1234) if seed is None else seed

        last_error: Exception | None = None
        for model in self.models:
            key = {"model": model, "prompt": prompt, "temperature": temperature,
                   "seed": seed, "json": json_mode}
            cached = self.cache.get(key)
            if cached is not None:
                log.debug("Gemini cache hit for %s", purpose)
                self._save_prompt(purpose, model, prompt, cached, key, from_cache=True)
                return extract_json(cached) if json_mode else cached

            service = f"gemini:{model}"
            if service not in self.quota.limits:
                self.quota.limits[service] = int(
                    self.cfg.get_path("quotas.gemini_requests_per_day", {}).get(
                        model, self.cfg.get_path("quotas.gemini_requests_per_day.default", 200)))
            try:
                self.quota.check(service, 1)
                text = self._call(model, prompt, temperature, seed, json_mode)
            except QuotaExceededError as exc:
                log.warning("  %s: free quota used up for today, trying next model…", model)
                last_error = exc
                continue
            except Exception as exc:  # noqa: BLE001
                code = _status_code(exc)
                if code == 429 and _is_daily_quota(exc):
                    self.quota.mark_exhausted(service)
                    log.warning("  %s: daily free limit reached, trying next model…", model)
                    last_error = exc
                    continue
                if code == 404:
                    log.warning("  %s is not available for your key, trying next model…", model)
                    last_error = exc
                    continue
                raise StudioError(f"Gemini request failed ({purpose}): {exc}",
                                  fix="Check your internet and GEMINI_API_KEY. "
                                  "Run: python studio.py doctor --online") from exc
            self.cache.set(key, text)
            self._save_prompt(purpose, model, prompt, text, key, from_cache=False)
            return extract_json(text) if json_mode else text

        raise QuotaExceededError(
            f"No Gemini model could answer ({purpose}). Last error: {last_error}",
            fix="Free daily limits reset at midnight Pacific time (~12:30 PM India time). "
            "Re-run then — finished work is kept. You can also add another free model "
            "to gemini.models in config.yaml (see `python studio.py doctor --online`).",
        )

    def _call(self, model: str, prompt: str, temperature: float, seed: int, json_mode: bool) -> str:
        from google.genai import types

        client = self._sdk()
        service = f"gemini:{model}"
        retry_cfg = self.cfg.get_path("retries", {})

        def once() -> str:
            self.quota.spend(service, 1)  # count attempts: failed calls also use quota
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    seed=seed,
                    response_mime_type="application/json" if json_mode else "text/plain",
                ),
            )
            text = getattr(resp, "text", None)
            if not text:
                raise StudioError("Gemini returned an empty answer (possibly blocked by its safety filter).",
                                  fix="Re-run; if it repeats, simplify the topic wording.")
            return text

        def retryable(exc: BaseException) -> bool:
            code = _status_code(exc)
            if code == 429 and _is_daily_quota(exc):
                return False
            return code in (429, 500, 502, 503, 504)

        return with_retries(
            once,
            attempts=int(retry_cfg.get("attempts", 5)),
            base_delay=float(retry_cfg.get("base_delay_s", 2.0)),
            max_delay=float(retry_cfg.get("max_delay_s", 60.0)),
            is_retryable=retryable,
            on_retry=lambda n, wait, e: log.info("  Gemini busy/rate-limited — waiting %.0fs (try %d)…", wait, n + 1),
        )

    def _save_prompt(self, purpose: str, model: str, prompt: str, response: str, key: dict,
                     from_cache: bool) -> None:
        if not self.prompts_dir:
            return
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        record = {"purpose": purpose, "model": model, "temperature": key["temperature"],
                  "seed": key["seed"], "from_cache": from_cache, "prompt": prompt, "response": response}
        name = f"{re.sub(r'[^a-z0-9]+', '_', purpose.lower())}_{hash_obj(key)[:10]}.json"
        (self.prompts_dir / name).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
