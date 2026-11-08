# 8. Streaming

`Agent.watch` in `app/packages/agent/graph.py` is what the chat route consumes. `ask` is `graph.invoke` and returns one dict. `watch` is:

```python
for mode, chunk in self.graph.stream(payload, config, stream_mode=["custom", "messages"]):
    if mode == "custom" and isinstance(chunk, dict):
        yield ("step", chunk)
    elif mode == "messages":
        text = extract_chunk_text(message)
        if text:
            yield ("token", text)
```

LangGraph runs the node on a worker when `messages` or `custom` is requested, and the caller can yield a chunk while the node is still running. That is why "Running a query…" is on the wire before the query returns. A sync `invoke` never does this. Do not switch the screen back to `ask()`.

## Custom events

`_emit` in `nodes/tools_node.py` writes the running event first, then the finished event with the same `id`. The screen upserts by that id, so the line changes in place from "Running a query…" to "Ran a query". [05-tools.md](05-tools.md) has the sentences.

`_emit` swallows errors. `invoke()` has no stream writer. That is intentional.

## Tokens

Token formatting and cleaning logic is isolated in `app/packages/agent/formatting.py`:

`extract_chunk_text` returns nothing for `tool`, `human`, or `system` messages, and nothing when the chunk has `tool_call_chunks`. Tool-call JSON must not appear in the answer.

Otherwise it returns visible text:

- a string is returned as-is, including a leading space
- a list of blocks drops `reasoning`, `thinking`, and `reasoning_content`, and joins the rest with no extra separator and no `strip`
- `clean_answer_text` is `clean_visible_text(...).strip()` and is only for the finished answer

Groq's content tokens look like `"Total"`, `" revenue"`, `":**"`, `" 2"`. Stripping each one produced `**Totalrevenue:**2,261,536.78` on screen. The stored answer was still `**Total revenue:** 2,261,536.78` because `clean_answer_text` strips the whole message once. Keep the space on the token.

If the messages stream yields nothing and the checker still produced an answer, `watch` yields that answer as one token before `("result", ...)`. An exception yields the single token `The model could not be reached.`

`on_llm_end` is deduped by message id, so the finished message is not appended a second time after the deltas. The `done` event still carries `answer` so the screen can replace the bubble with the stored sentence. See [01-entry.md](01-entry.md) and [09-screen.md](09-screen.md).

Reasoning tokens arrive as empty `content` over a few hundred milliseconds, then the answer tokens arrive in a burst (tens of milliseconds for a short sentence). The UI shows tool lines during the tool, then the answer as those content tokens land. Empty reasoning chunks are not events.

`test_loop.py` asserts that a scripted `watch` yields `running` before `ok`, and that `extract_chunk_text(AIMessageChunk(content=" revenue"))` is still `" revenue"`.
