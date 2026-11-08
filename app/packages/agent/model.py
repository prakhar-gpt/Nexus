"""The one hosted model the agent calls. The first configured key wins."""

from __future__ import annotations

import os
from pathlib import Path

from langchain_openai import ChatOpenAI

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

# Groq's current tool-calling model. Llama 3.3 was retired for this tier.
PROVIDERS = (
    ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
)


class ModelError(RuntimeError):
    pass


def _secret(name: str) -> str:
    value = os.environ.get(name, "").strip().strip('"').strip("'")
    if value:
        return value
    if not ENV_PATH.exists():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def resolve() -> tuple[str, str, str, str]:
    for label, key_name, base_url, model in PROVIDERS:
        secret = _secret(key_name)
        if secret:
            return label, secret, base_url, model
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
        temperature=0,
        max_tokens=800,
    )
    return Hosted(client, f"{label}/{model}")
