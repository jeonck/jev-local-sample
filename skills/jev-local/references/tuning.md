# Tuning transcript — reference run

Support-ticket triage, 10 tickets, questions: department (5-way choice), severity (3-level score),
wants_refund (noul). Gate: confidence < 0.6 → human; severity ≥ MAJOR → human; else auto-route.
Repo: https://github.com/jeonck/jev-local-sample

## Run 1 — Qwen2.5-1.5B-Instruct-4bit (5 s / 10 tickets)

```
T-001  human     billing    0.46 1.03   low confidence   ← size mismatch, should be returns
T-002  shipping  shipping   0.98 1.28
T-006  billing   billing    0.66 1.20                    ← "do you ship to Canada?", should be sales/shipping
T-010  human     returns    0.53 1.00   low confidence
```

Almost everything collapses to `billing`, confidence hovers near 0.5. Auto rate 2/10. The gate does its
job (ambiguous → human) but the model is not judging. **Switch model before touching anything else.**

## Run 2 — gemma-3-4b-it-4bit, MAJOR = 1.5 (18 s / 10 tickets)

```
T-001  returns   returns    1.00 1.01
T-002  human     shipping   1.00 1.99   major severity   ← 9-day delivery delay
T-004  technical technical  1.00 1.01
T-005  human     billing    0.93 2.00   major severity   ← heater smoking, outlet melted (correct)
T-007  human     returns    0.32 0.06   low confidence   ← ticket text is "hi" (correct)
T-008  human     billing    1.00 2.00   major severity   ← crushed box, broken mug
T-009  human     technical  1.00 2.00   major severity   ← locked out of account
```

Departments now right on 9/10. Severity is the problem: every negative ticket is pushed to major.

## Run 3 — MAJOR = 1.9

Identical output. Raw probabilities for T-002: `{"0": 0.00004, "1": 0.016, "2": 0.984}`. Scores are
bimodal (≈1.0 or ≈2.0), so the threshold position between them is irrelevant. **Thresholds cannot fix a
decided model.**

## Run 4 — narrow `major` only

```
"major: physical injury risk, fire, or money already lost"    (was: safety hazard, outage, or financial loss)
```

T-006 dropped 0.90 → 0.03, so wording is being read — but T-002/008/009 stayed at ≈2.0. Narrowing the
wrong bucket is not enough when the right bucket does not name the case.

## Run 5 — enumerate the moderate cases

```
"moderate: wrong or broken item, late or lost delivery, login trouble, duplicate charge"
```

```
T-002  shipping  shipping   1.00 1.04
T-003  billing   billing    1.00 1.00   (refund flag True)
T-005  human     billing    0.93 2.00   major severity
T-007  human     returns    0.32 0.05   low confidence
T-008  billing   billing    1.00 1.01
T-009  technical technical  1.00 1.00
```

Auto rate 8/10; the two human items are the only ones that should be. Nothing else changed.

## Takeaways

1. Small models: check the choice question first — if one option absorbs everything, change model.
2. Print `probabilities` before adjusting a threshold; if mass ≥ 0.95 on one level, the threshold is moot.
3. Name the cases in the bucket you want them in. Narrowing the neighbouring bucket is weaker.
4. Zero-shot `confidence` of 1.00 is the norm with Gemma 3 4B, not a signal. Only a trained head gives a
   calibrated one (open-jev reports ECE 0.03 after `make train`).
