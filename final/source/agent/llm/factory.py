from agent.llm.bedrock import BedrockClient
from agent.llm.config import LLMConfigurationError, LLMSettings
from agent.llm.contract import LLMClient, ScriptedLLMClient
from agent.llm.gemini import GeminiClient
from agent.llm.groq import GroqClient
from agent.llm.nvidia import NvidiaNIMClient
from agent.llm.openrouter import OpenRouterClient


def build_llm_client(settings: LLMSettings) -> LLMClient:
    if settings.provider == "scripted":
        return ScriptedLLMClient()
    if settings.provider == "nvidia":
        return NvidiaNIMClient(settings)
    if settings.provider == "groq":
        return GroqClient(settings)
    if settings.provider == "gemini":
        return GeminiClient(settings)
    if settings.provider == "openrouter":
        return OpenRouterClient(settings)
    if settings.provider == "bedrock":
        return BedrockClient(settings)
    raise LLMConfigurationError(
        f"The {settings.provider} LLM adapter is not available in this build"
    )
