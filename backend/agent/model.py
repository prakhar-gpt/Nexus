"""The one hosted model the agent calls. Configured via config.settings or environment."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

try:
    from config import settings
except Exception:
    from backend.config import settings


PROVIDERS = (
    ("groq", "GROQ_API_KEY", settings.GROQ_BASE_URL, settings.GROQ_DEFAULT_MODEL),
    ("openrouter", "OPENROUTER_API_KEY", settings.OPENROUTER_BASE_URL, settings.OPENROUTER_DEFAULT_MODEL),
    ("deepseek", "DEEPSEEK_API_KEY", settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_DEFAULT_MODEL),
)


class ModelError(RuntimeError):
    pass


def resolve() -> tuple[str, str, str, str]:
    """Resolve the active LLM provider, secret key, base URL, and model name from settings."""
    chosen = (settings.MODEL_PROVIDER or "").lower().strip()
    override_model = settings.MODEL_NAME.strip()

    provider_map = {
        "groq": (settings.GROQ_API_KEY, settings.GROQ_BASE_URL, settings.GROQ_DEFAULT_MODEL),
        "openrouter": (settings.OPENROUTER_API_KEY, settings.OPENROUTER_BASE_URL, settings.OPENROUTER_DEFAULT_MODEL),
        "deepseek": (settings.DEEPSEEK_API_KEY, settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_DEFAULT_MODEL),
    }

    if chosen:
        if chosen not in provider_map:
            raise ModelError(f"Unknown provider '{chosen}'. Valid providers: {', '.join(provider_map.keys())}")
        secret, base_url, default_model = provider_map[chosen]
        if not secret:
            raise ModelError(f"No key configured for provider '{chosen}'.")
        return chosen, secret, base_url, override_model or default_model

    for name, (secret, base_url, default_model) in provider_map.items():
        if secret:
            return name, secret, base_url, override_model or default_model

    raise ModelError("No model key is configured.")


class Hosted:
    """A chat client plus the name we store on a run. The key stays inside the client."""

    def __init__(self, client: ChatOpenAI, name: str):
        self.client = client
        self.nexus_name = name

    def bind_tools(self, tools):
        return Hosted(self.client.bind_tools(tools), self.nexus_name)

    def invoke(self, messages):
        return self.client.invoke(messages)


def chat_model() -> Hosted:
    label, secret, base_url, model = resolve()
    client = ChatOpenAI(
        api_key=secret,
        base_url=base_url,
        model=model,
        streaming=True,
        temperature=settings.MODEL_TEMPERATURE,
        max_tokens=settings.MODEL_MAX_TOKENS,
    )
    return Hosted(client, f"{label}/{model}")
