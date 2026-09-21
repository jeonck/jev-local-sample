# POST /v1/systemone

Same contract as TypeSafe's System One (docs.typesafe.ai). open-jev serves it locally.
Set `OPENJEV_API_KEY` before `make serve` to require `Authorization: Bearer <key>`; otherwise any value works.

## Request

```json
{
  "state": "<string | object | array>",
  "model": "jev-latest",
  "questions": {
    "<id>": {"type": "choice", "instructions": "...", "criteria": {"opt_a": "description", "opt_b": "description"}},
    "<id>": {"type": "score",  "instructions": "...", "criteria": ["level 0 description", "level 1 description", "level 2 description"]},
    "<id>": {"type": "noul",   "instructions": "..."}
  }
}
```

- `state` — the thing being judged. A dict like `{"document": "...", "metadata": {...}}` is rendered as a block.
- `choice.criteria` — up to 255 options. Description may be a string, object, array or `null`.
- `score.criteria` — ordered; index 0 is the lowest level. Descriptions become the `legend`.
- `noul.criteria` — optional `{"true": "...", "false": "..."}` to describe what yes/no mean.

## Response

```json
{
  "model": "jev-latest",
  "answers": {
    "<choice id>": {"type": "choice", "choice": "opt_a", "probabilities": {"opt_a": 0.83, "opt_b": 0.17}, "confidence": 0.58},
    "<score id>":  {"type": "score", "score": 1.02, "confidence": 0.90,
                    "legend": {"0": "level 0 description", "1": "...", "2": "..."},
                    "probabilities": {"0": 0.0001, "1": 0.977, "2": 0.023}},
    "<noul id>":   {"type": "noul", "noul": 0.012}
  },
  "usage": {"input_tokens": 165, "output_tokens": 8}
}
```

- `score` = Σ index × probability (so 1.02 means "almost exactly level 1").
- `confidence` = 1 − normalised entropy of `probabilities` in open-jev. TypeSafe does not publish theirs.
- `usage.output_tokens` counts scored label tokens; nothing is generated.

## How open-jev computes it

Each question is rendered to a plain-text prompt: state block, instructions, the options (or levels, or
yes/no), then `Answer:`. The option names / level numbers / `yes`,`no` are scored as continuations in one
prefix-shared batched forward pass, softmaxed. This is why the *wording of criteria* is the dominant lever:
the model is literally comparing your descriptions against the state.

## Other endpoints

- `GET /health` → `{"ok": true, "model": "...", "load_s": ...}`
- `POST /score` → raw option scoring: `{"context": "...", "options": ["...", "..."], "norm": "mean"}`.
  Lower-level than systemone; use it when you want to score free-form continuations.

## SDK equivalents

Set `TYPESAFE_BASE_URL=http://127.0.0.1:8000` and `TYPESAFE_API_KEY=anything`, then:

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
with TypeSafeClient() as client:
    r = client.system_one(state={"document": text}, questions={
        "billing": Noul(instructions="Is this ticket about billing?"),
        "tone": Choice(instructions="Customer's tone?", criteria={"calm": None, "frustrated": None, "angry": None}),
        "urgency": Score(instructions="How urgent?", criteria=["can wait", "this week", "today"]),
    })
```

`langchain-typesafe` exposes the same as `TypeSafeClassifier` and a `ModelRouterMiddleware` that picks a
model per request from `ModelChoice(model=..., criteria=...)` entries — the "use jev to route to a
generator" pattern.
