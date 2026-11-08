# 3. The thread

One workspace is one LangGraph thread. `_prepare` in `graph.py` sets:

```python
config = {
    "configurable": {"thread_id": thread_id or f"workspace-{int(workspace_id)}"},
    "recursion_limit": 30,
}
```

The screen does not pass `thread_id`, so a room uses `workspace-1`, `workspace-2`, and so on. Tests pass their own ids (`loop-revenue`, `probe-stream-tools`) so they do not write into the room the user is chatting with.

The checkpointer is `MemorySaver`, compiled once in `Agent.__init__`. It dies with the process.

On each question `_prepare` loads that thread:

- If the checkpoint already has messages, the new input is only the new `HumanMessage`. The older turns are already in the checkpoint.
- If the checkpoint is empty, it prepends `_history(workspace_id)` unless the caller passed `history=` (tests pass `[]` so they do not read `runs`).

`_history` reads the last 8 rows (`HISTORY_TURNS`) for that workspace, oldest last, and turns each into a human message plus an assistant message. It does not reload tool calls or SQL. After a restart the model knows what was asked and what was answered. It does not know which query produced the number. The prompt tells it to query again.

Every question also sends a fresh payload:

```python
payload = {
    "messages": incoming,
    "workspace_id": int(workspace_id),
    "rows": [],
    "sqls": [],
    "steps": [],
    "step_count": 0,
}
```

`rows`, `sqls`, `steps`, and `step_count` are this turn only. The checker in [07-checker.md](07-checker.md) sees only the rows collected after this payload. A number copied from an earlier answer fails the check unless this turn's tool output contains it too.

`workspace_id` is state. It is not a tool argument. The tools node reads `state["workspace_id"]` and passes it to `execute_sql`. The model never supplies it.

The agent node only shows the model the last 30 messages (`MESSAGE_TAIL`), plus the system prompt prepended on that call. The system prompt is not stored in the checkpoint.
