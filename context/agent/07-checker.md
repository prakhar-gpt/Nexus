# 7. The checker

The checker node is the only way out of the graph. It does not call a model.

```python
if last message still has tool_calls:
    answer = "The step limit was reached before an answer."
else:
    answer = _text(last) or "No answer was produced."
check = check_answer(answer, rows)
```

`_text` is the full assistant message with reasoning blocks removed and the ends stripped. Internal spaces stay. This string is what `runs.answer` stores. It is not the concatenation of stripped tokens. That difference is why a refresh used to look better than the live bubble. [08-stream.md](08-stream.md) keeps the tokens intact, and the `done` event sends this stored sentence back.

`kind`:

- `sql` when this turn ran at least one query
- `refusal` when the answer contains `cannot answer` or `refus`
- `unknown` otherwise (a greeting, a definition with no query)

`check_answer` in `app/packages/agent/checker.py` pulls every number out of the answer and out of the tool rows. A number matches if the decimals are equal. Thousands separators are stripped first, so `2,261,536.78` matches `2261536.78`. `verified` is true when `untraced` is empty.

The node appends a step `{tool: "checker", status: "ok" | "caveat"}`. The screen does not show that step. It uses `verified` to decide the caveat sentence. A verified answer has no badge. An unverified answer gets a caveat under the text. The number is still shown. The checker does not delete it. See [09-screen.md](09-screen.md).

`draft_from_rows` writes `column=value` lines. Only `app/eval/runner.py` uses it, as the draft the golden set checks. The live agent must not answer in that shape. The prompt forbids `subcategories=17`.

What the checker does not do:

- It does not re-run the SQL.
- It does not judge whether the SQL was the right question. The golden set does that, offline.
- It does not see rows from an earlier turn. Those lists were wiped in [03-thread.md](03-thread.md).
- It does not call a model. Narrative judging is out of scope.
