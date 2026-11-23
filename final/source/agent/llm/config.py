from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from os import environ
from typing import Literal

from dotenv import load_dotenv
from pydantic import SecretStr


class LLMConfigurationError(ValueError):
    """The selected model provider cannot start with the supplied configuration."""


@dataclass(frozen=True)
class LLMSettings:
    provider: Literal["scripted", "nvidia", "groq", "gemini", "openrouter", "bedrock"]
    model: str
    api_key: SecretStr | None = None
    endpoint: str | None = None
    timeout_seconds: float = 20
    stream: bool = False
    reasoning_effort: str | None = None
    openrouter_total_limit: float = 0.25
    region: str | None = None


def load_llm_settings(environment: Mapping[str, str] | None = None) -> LLMSettings:
    if environment is None:
        load_dotenv()
    values = environ if environment is None else environment
    provider = values.get("LLM_PROVIDER", "").strip()
    if not provider:
        raise LLMConfigurationError("LLM_PROVIDER is required")
    model = values.get("LLM_MODEL", "").strip()
    if not model:
        raise LLMConfigurationError("LLM_MODEL is required")
    if provider not in {"scripted", "nvidia", "groq", "gemini", "openrouter", "bedrock"}:
        raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {provider}")
    api_key_name = "GROQ_API_KEY" if provider == "groq" else "NVIDIA_API_KEY"
    if provider == "gemini":
        api_key_name = "GEMINI_API_KEY"
    if provider == "openrouter":
        api_key_name = "OPENROUTER_API_KEY"
    api_key_text = values.get(api_key_name, "").strip()
    if provider == "nvidia" and not api_key_text:
        raise LLMConfigurationError("NVIDIA_API_KEY is required for the nvidia provider")
    if provider == "groq" and not api_key_text:
        raise LLMConfigurationError("GROQ_API_KEY is required for the groq provider")
    endpoint = None
    timeout_seconds = 20.0
    stream = False
    reasoning_effort = None
    openrouter_total_limit = 0.25
    region = None
    if provider == "bedrock":
        api_key_text = ""
        region = values.get("AWS_REGION", "").strip()
        if region != "eu-north-1" or model != "openai.gpt-oss-20b-1:0":
            raise LLMConfigurationError("Bedrock requires the explicit Stockholm candidate")
        try:
            timeout_seconds = float(values.get("LLM_TIMEOUT_SECONDS", "20"))
        except ValueError as error:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be a number") from error
        if not isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
            raise LLMConfigurationError("Bedrock timeout must be finite and at most 60 seconds")
    if provider == "openrouter":
        if not api_key_text:
            raise LLMConfigurationError("OPENROUTER_API_KEY is required")
        endpoint = "https://openrouter.ai/api/v1"
        timeout_seconds = 30.0
        try:
            openrouter_total_limit = float(values.get("OPENROUTER_TOTAL_CAP_DOLLARS", "0.25"))
        except ValueError as error:
            raise LLMConfigurationError("OPENROUTER_TOTAL_CAP_DOLLARS must be a number") from error
        if not isfinite(openrouter_total_limit) or not 0 < openrouter_total_limit <= 2.00:
            raise LLMConfigurationError("OpenRouter total cap must be between $0 and $2.00")
    if provider == "gemini":
        if not api_key_text:
            raise LLMConfigurationError("GEMINI_API_KEY is required for the gemini provider")
        endpoint = "https://generativelanguage.googleapis.com/v1beta"
        try:
            timeout_seconds = float(values.get("LLM_TIMEOUT_SECONDS", "30"))
        except ValueError as error:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be a number") from error
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be finite and positive")
    if provider == "nvidia":
        endpoint = values.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
        if not endpoint:
            raise LLMConfigurationError("NVIDIA_BASE_URL must not be empty")
        try:
            timeout_seconds = float(values.get("LLM_TIMEOUT_SECONDS", "20"))
        except ValueError as error:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be a number") from error
        if timeout_seconds <= 0:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be positive")
        stream_text = values.get("NVIDIA_STREAM", "false").strip().lower()
        if stream_text not in {"true", "false"}:
            raise LLMConfigurationError("NVIDIA_STREAM must be true or false")
        stream = stream_text == "true"
    if provider == "groq":
        endpoint = values.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
        if not endpoint:
            raise LLMConfigurationError("GROQ_BASE_URL must not be empty")
        try:
            timeout_seconds = float(values.get("LLM_TIMEOUT_SECONDS", "20"))
        except ValueError as error:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be a number") from error
        if timeout_seconds <= 0:
            raise LLMConfigurationError("LLM_TIMEOUT_SECONDS must be positive")
        reasoning_effort = values.get("LLM_REASONING_EFFORT", "none").strip().lower()
        if reasoning_effort not in {"none", "low", "medium", "high"}:
            raise LLMConfigurationError("LLM_REASONING_EFFORT must be none, low, medium, or high")
    return LLMSettings(
        provider=provider,
        model=model,
        api_key=SecretStr(api_key_text) if api_key_text else None,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        stream=stream,
        reasoning_effort=reasoning_effort,
        openrouter_total_limit=openrouter_total_limit,
        region=region,
    )
