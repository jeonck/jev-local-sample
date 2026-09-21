---
name: jev-local
description: Run TypeSafe-style structured judgment (jev / System One API) locally with open-jev on Apple silicon, and design confidence-gated classification on top of it — choice / score / noul questions answered with probabilities, no text generation. Use this whenever the user mentions jev, TypeSafe, open-jev, systemone, "구조화 판단", or wants to classify / route / triage / rank / gate many items against a fixed set of options with a local model and a confidence threshold (ticket triage, log or alert routing, PR labeling, document routing, LLM model routers or guardrails, "확신 없으면 사람에게" flows). Also use it when someone wants to validate question design locally before calling the paid TypeSafe API. Do not use it for tasks that need generated text.
---

# jev-local

jev (TypeSafe) answers typed questions about a `state` with probabilities instead of generating text.
open-jev (https://github.com/daseinlabs/open-jev) implements the same `POST /v1/systemone` contract
with a local MLX model. One prefix-shared forward pass per question, no decoding, ~50–600 ms depending
on model — so it fits where a generative LLM is overkill: high-volume, repeated classification with a
fixed option set, plus a `confidence` you can branch on.

The three question types, and what they are good for:

| type | criteria | answer | use it for |
|---|---|---|---|
| `choice` | `{name: description}` map | `choice`, `probabilities`, `confidence` | which bucket / department / handler |
| `score` | ordered list of level descriptions | `score` (prob-weighted level index), `probabilities`, `confidence` | severity, urgency, priority on a scale |
| `noul` | none, or `{"true": .., "false": ..}` | `noul` = P(yes) | a single boolean flag |

Full request/response shape: `references/systemone.md`.

## Workflow

### 1. Bring up the server

Apple silicon only (MLX, Metal). Needs `uv` and the `hf` CLI. Copy `assets/Makefile` into the project
and run `make setup && make serve`. It clones open-jev into `./open-jev/`, creates its venv and downloads
the model. Add `open-jev/` to `.gitignore` — it holds a multi-GB model.

Model choice matters more than anything else in this skill:

- **`mlx-community/gemma-3-4b-it-4bit`** (default in the Makefile): the one to use. open-jev's own default,
  `google/gemma-3-4b-it`, is gated on Hugging Face and needs a login; the mlx-community 4-bit conversion is
  ungated, already in MLX format, ~2.5 GB, loads in ~8 s, ~0.6 s per question.
- **`mlx-community/Qwen2.5-1.5B-Instruct-4bit`**: 3× faster but collapses choice questions onto one option
  (everything became "billing" in a 5-way department test) with confidence around 0.5. Fine for checking that
  the pipeline runs, not for judging anything.

`make health` should return `{"ok": true, "model": ...}` before you go further.

### 2. Write the questions

Put the item text (or a dict/list) in `state` and ask 2–4 questions in one request — the prefix is shared, so
extra questions are cheap. Start from `assets/client.py`: `judge()` posts to `/v1/systemone` with stdlib
`urllib`, `decide()` holds the routing rule. Keep the SDK out unless the project already has it; the HTTP
contract is small and `TYPESAFE_BASE_URL` / `TYPESAFE_API_KEY` are the same env vars `typesafe_sdk` and
`langchain-typesafe` read, so a project can switch from local to the paid API by changing one variable.

Write criteria descriptions as **lists of concrete cases**, not abstract labels. jev scores option
descriptions against the state directly; "moderate: wrong or broken item, late or lost delivery, login
trouble" separates far better than "moderate: a significant problem". This is the main lever you have —
see step 4 before reaching for thresholds.

### 3. Add the confidence gate

The `confidence` field (1 − normalised entropy in open-jev; TypeSafe's formula is unpublished) is what makes
jev useful beyond a plain classifier. The usual shape:

```python
if dept["confidence"] < THRESHOLD:  route = "human"      # model unsure
elif sev["score"] >= MAJOR:         route = "human"      # too important to automate
else:                               route = dept["choice"]
```

Decide the direction of the gate from the cost of a wrong automatic action. For support tickets,
"confident → auto, else human" is fine. For anything safety- or money-critical, invert it: the model only
*orders* the options a human sees (top-1 when confident, top-3 when not) and never acts alone. Zero-shot
confidence is not calibrated — Gemma 3 4B returns 1.00 on most items — so a threshold protects against
*ambiguity*, not against *confident errors*.

### 4. Tune — in this order

1. **Print the raw `probabilities`** for a misclassified item. If the mass sits at 0.98 on one option, no
   threshold will move it; the model has decided. Go to 2.
2. **Rewrite criteria** with the cases that are landing in the wrong bucket named explicitly in the right
   one. In the reference run, widening `major` alone did nothing (a shipping delay stayed at P(major)=0.98);
   enumerating the moderate cases moved three items from 2.0 to 1.0 and left only the real hazard at major.
3. **Then** adjust thresholds. `score` answers from small models are often bimodal (1.0 or 2.0, nothing
   between), which is why threshold changes can have zero effect.
4. If it is still wrong, or you need calibrated confidence, the project needs labelled data and open-jev's
   trained head (`make features`, `make train`, `make eval-head` in the open-jev repo — ECE ≈ 0.03 on their
   synthetic split vs. no calibration zero-shot). That is a real project, not a tweak.

`references/tuning.md` has the full before/after transcript of the reference run to compare against.

### 5. Leave a check behind

`decide()` is a branch — keep a stdlib `assert`-style test of it that runs without the server (see the
bottom of `assets/client.py`). A batch run should also write its decisions to a JSONL file so a human can
audit the routing later.

## What jev is not for

- Anything that needs generated text (summaries, replies, explanations). Pair it with a generator instead:
  jev decides *which* template or model, the generator writes.
- Open-ended labels. Every option has to be written down in advance (choice supports up to 255).
- Linux or CUDA. open-jev is MLX-only; on other platforms use the TypeSafe API directly with the same client.
