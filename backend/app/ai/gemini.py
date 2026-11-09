"""Google Gemini implementation of the shared AI provider contract."""

import asyncio
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from weakref import WeakKeyDictionary
from typing import Any, TypeVar

from pydantic import BaseModel

from ..config import settings
from .errors import AIUnavailableError
from .prompts import PROFILE_SYSTEM, SCORECARD_SYSTEM, SCORE_SYSTEM, TRANSCRIBE_SYSTEM
from .schemas import Profile, ScoreResult, ScorecardDraft, TranscriptionResult

SchemaT = TypeVar("SchemaT", bound=BaseModel)
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 60
_semaphores: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()
_request_pacing: WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[asyncio.Lock, float]] = WeakKeyDictionary()


def _request_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max(1, settings.ai_concurrency))
        _semaphores[loop] = semaphore
    return semaphore


async def _pace_request() -> None:
    interval = max(0.0, settings.gemini_request_interval_seconds)
    if interval == 0:
        return
    loop = asyncio.get_running_loop()
    pacing = _request_pacing.get(loop)
    if pacing is None:
        pacing = (asyncio.Lock(), 0.0)
        _request_pacing[loop] = pacing
    lock = pacing[0]
    async with lock:
        last_request_at = _request_pacing.get(loop, (lock, 0.0))[1]
        delay = interval - (loop.time() - last_request_at)
        if delay > 0:
            await asyncio.sleep(delay)
        _request_pacing[loop] = (lock, loop.time())


def _status_code(error: Exception) -> int | None:
    value = getattr(error, "code", None) or getattr(error, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_retryable(error: Exception) -> bool:
    status = _status_code(error)
    return status is not None and 500 <= status < 600


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    raw_value = headers.get("Retry-After") if headers is not None else None
    if raw_value is None:
        return None
    try:
        return max(0.0, float(raw_value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(str(raw_value))
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class GeminiProvider:
    """Structured Google Gen AI calls with bounded concurrency and transient retries."""

    def __init__(self) -> None:
        self.model = settings.gemini_model

    def _client(self) -> Any:
        if not settings.gemini_api_key:
            raise AIUnavailableError("Gemini is selected but GEMINI_API_KEY is missing.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise AIUnavailableError("Gemini SDK is unavailable. Install backend requirements and retry.") from error

        return genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(attempts=0),
            ),
        )

    async def _generate(
        self,
        schema: type[SchemaT],
        system_instruction: str,
        contents: str | list[Any],
    ) -> SchemaT:
        for attempt in range(MAX_ATTEMPTS):
            try:
                from google.genai import types

                async with _request_semaphore():
                    async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                        await _pace_request()
                        sdk_client = self._client()
                        async with sdk_client.aio as client:
                            response = await client.models.generate_content(
                                model=self.model,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_instruction,
                                    response_mime_type="application/json",
                                    response_schema=schema,
                                    temperature=0,
                                ),
                            )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed
                if parsed is not None:
                    return schema.model_validate(parsed)
                response_text = getattr(response, "text", None)
                if not response_text:
                    raise ValueError("Gemini returned an empty structured response.")
                return schema.model_validate_json(response_text)
            except Exception as error:
                if isinstance(error, AIUnavailableError):
                    raise
                status = _status_code(error)
                if status == 429:
                    raise AIUnavailableError(
                        "Gemini rate limit reached.",
                        status_code=429,
                        retry_after_seconds=_retry_after_seconds(error),
                    ) from error
                if _is_retryable(error) and attempt + 1 < MAX_ATTEMPTS:
                    delay = 0.5 * (2**attempt) + random.uniform(0, 0.25 * (2**attempt))
                    await asyncio.sleep(delay)
                    continue
                if status == 429 or (status is not None and status >= 500):
                    detail = f"Gemini is temporarily unavailable after retries (HTTP {status})."
                elif status in (401, 403):
                    detail = f"Gemini rejected its API credentials (HTTP {status}); check GEMINI_API_KEY."
                elif status is not None:
                    detail = f"Gemini rejected the request (HTTP {status}); check GEMINI_MODEL and the response schema."
                else:
                    detail = "Gemini request failed; check the provider configuration and retry."
                raise AIUnavailableError(detail, status_code=status) from error
        raise AIUnavailableError("Gemini request failed after retries.")

    async def extract_scorecard(self, jd: str) -> ScorecardDraft:
        return await self._generate(ScorecardDraft, SCORECARD_SYSTEM, jd)

    async def extract_profile(self, text: str) -> Profile:
        return await self._generate(Profile, PROFILE_SYSTEM, f"<cv>\n{text}\n</cv>")

    async def score_cv(self, text: str, scorecard: dict[str, Any]) -> ScoreResult:
        import json

        contents = f"<cv>\n{text}\n</cv>\nScorecard:\n{json.dumps(scorecard, ensure_ascii=False)}"
        return await self._generate(ScoreResult, SCORE_SYSTEM, contents)

    async def transcribe_scan(self, data: bytes) -> str:
        try:
            from google.genai import types
        except ImportError as error:
            raise AIUnavailableError("Gemini SDK is unavailable. Install backend requirements and retry.") from error

        contents = [
            types.Part.from_text(text="Transcribe the attached CV exactly, preserving its line breaks."),
            types.Part.from_bytes(data=data, mime_type="application/pdf"),
        ]
        result = await self._generate(TranscriptionResult, TRANSCRIBE_SYSTEM, contents)
        return result.text
