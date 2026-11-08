# 2. The model

`backend/agent/model.py` picks the first configured key. Order is fixed (Decision 22):

| Label | Env var | Base URL | Model id |
|---|---|---|---|
| groq | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` |
| openrouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` |
| deepseek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` | `deepseek-chat` |

`_secret` reads that one variable from the environment, or the matching line in the repo `.env`. It never logs the value. Do not read the rest of `.env` into a note or a reply.

`ChatOpenAI` is a pydantic model and rejects an extra field. The name we store on `runs` therefore sits on a wrapper:

```python
class Hosted:
    def bind_tools(self, tools):
        return Hosted(self.client.bind_tools(tools), self.nexus_name)

    def invoke(self, messages):
        return self.client.invoke(messages)
```

`nexus_name` is `groq/openai/gpt-oss-120b` when Groq wins. Scripted tests have no `nexus_name`; the graph stores `"scripted"`.

`chat_model()` builds the client with `streaming=True`, `temperature=0`, and `max_tokens=800`. `streaming=True` is what lets LangGraph's `messages` mode see tokens during `invoke`. Without it, the answer arrives as one blob after the call returns.

`openai/gpt-oss-120b` does not support parallel tool calls. The prompt says one tool at a time. It also spends most of its output budget on reasoning tokens that are not the answer. Those chunks have empty `content` and show up in `usage_metadata.output_token_details.reasoning`. The visible answer is a short burst afterwards. See [08-stream.md](08-stream.md).

Llama 3.3 (`llama-3.3-70b-versatile`) was retired for this Groq tier. Do not put it back.

The client is created when `graph.py` is imported. A new key or a new model id requires an API restart.
