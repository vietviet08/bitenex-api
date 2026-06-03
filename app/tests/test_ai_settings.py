from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from app.modules.admin import ai_settings


def _rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    response = httpx.Response(
        status_code=429,
        headers=headers,
        request=httpx.Request("POST", "https://provider.test/v1/chat/completions"),
    )
    return RateLimitError(
        "quota exhausted",
        response=response,
        body={"error": {"message": "quota exhausted"}},
    )


class _FakeChatCompletions:
    def __init__(self, failures_before_success: int):
        self.calls = 0
        self.failures_before_success = failures_before_success

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise _rate_limit_error("0.25")
        return {"ok": True, "kwargs": kwargs}


@pytest.mark.asyncio
async def test_chat_completion_retries_provider_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    completions = _FakeChatCompletions(failures_before_success=1)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(ai_settings.asyncio, "sleep", fake_sleep)

    result = await ai_settings.create_chat_completion_with_retry(
        client,  # type: ignore[arg-type]
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=100,
        temperature=0,
        retry_attempts=3,
    )

    assert result["ok"] is True
    assert completions.calls == 2
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_chat_completion_raises_after_retry_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sleep(delay: float) -> None:
        return None

    completions = _FakeChatCompletions(failures_before_success=3)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(ai_settings.asyncio, "sleep", fake_sleep)

    with pytest.raises(RateLimitError):
        await ai_settings.create_chat_completion_with_retry(
            client,  # type: ignore[arg-type]
            model="test-model",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            temperature=0,
            retry_attempts=3,
        )

    assert completions.calls == 3
