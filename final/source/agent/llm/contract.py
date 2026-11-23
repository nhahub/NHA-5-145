from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "shopper", "assistant", "tool"]
    content: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class LLMChunk:
    text: str | None = None
    tool_call: LLMToolCall | None = None

    def __post_init__(self) -> None:
        if (self.text is None) == (self.tool_call is None):
            raise ValueError("An LLM chunk must contain text or one tool call")


@dataclass(frozen=True)
class LLMRequest:
    system: str
    messages: tuple[LLMMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    response_schema: Mapping[str, Any] | None = None
    response_validator: Callable[[str], object] | None = None
    prompt_version: str = "unversioned"
    schema_version: int | None = None
    temperature: float = 0
    max_tokens: int = 512
    # Local telemetry correlation only; never transmitted as model instructions.
    attempt_id: str | None = None
    # Coordinators can own retries and prohibit hidden provider attempts.
    provider_attempt_limit: Literal[1, 2] = 2
    # Local runtime authority only; never serialized into prompts or provider payloads.
    authorization_check: Callable[[], Awaitable[None]] | None = None

    async def authorize(self) -> None:
        if self.authorization_check is not None:
            await self.authorization_check()


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]: ...


class LLMInvalidResponseError(ValueError):
    """The provider answered, but the completion cannot be interpreted as model output."""


class ScriptedLLMClient:
    def __init__(self, responses: Iterable[Iterable[LLMChunk]] = ()) -> None:
        self._responses = iter(tuple(tuple(response) for response in responses))

    async def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        del request
        try:
            chunks = next(self._responses)
        except StopIteration as error:
            raise RuntimeError("The scripted LLM has no response for this request") from error
        for chunk in chunks:
            yield chunk
