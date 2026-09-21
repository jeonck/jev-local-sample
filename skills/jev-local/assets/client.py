#!/usr/bin/env python3
"""Minimal jev client + confidence gate. stdlib only.

judge(text)   -> answers dict from POST /v1/systemone
decide(answers) -> routing decision; edit the rule for your domain
Run `python3 client.py --test` to check decide() without a server.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("TYPESAFE_API_KEY", "local")
THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.6"))
MAJOR = 1.9  # score level at/above which a human must look; print raw probabilities before tuning this

# Describe criteria as lists of concrete cases — jev matches these descriptions against the state.
QUESTIONS = {
    "bucket": {
        "type": "choice",
        "instructions": "Which handler should take this item?",
        "criteria": {
            "a": "concrete cases that belong to a",
            "b": "concrete cases that belong to b",
            "other": "anything that fits none of the above",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How severe is this?",
        "criteria": [
            "minor: concrete minor cases",
            "moderate: concrete moderate cases (name the ones that keep getting rated major)",
            "major: narrow, concrete major cases",
        ],
    },
    "flag": {"type": "noul", "instructions": "Is <condition> explicitly present?"},
}


def judge(state) -> dict:
    body = json.dumps({"state": state, "model": "jev-latest", "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/systemone",
        body,
        {"content-type": "application/json", "authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["answers"]


def decide(answers: dict, threshold: float = THRESHOLD) -> dict:
    bucket, sev, flag = answers["bucket"], answers["severity"], answers["flag"]
    d = {
        "bucket": bucket["choice"],
        "confidence": round(bucket["confidence"], 2),
        "severity": round(sev["score"], 2),
        "flag": flag["noul"] >= 0.5,
    }
    if bucket["confidence"] < threshold:
        d["route"], d["reason"] = "human", "low confidence"
    elif sev["score"] >= MAJOR:
        d["route"], d["reason"] = "human", "major severity"
    else:
        d["route"], d["reason"] = bucket["choice"], ""
    return d


def run(path: str) -> None:
    items = [json.loads(l) for l in open(path) if l.strip()]
    with open("decisions.jsonl", "w") as out:
        for it in items:
            try:
                d = decide(judge(it["text"]))
            except urllib.error.URLError as e:
                sys.exit(f"cannot reach jev at {BASE_URL} ({e.reason}). Run `make serve` first.")
            print(f"{it.get('id', ''):8} {d['route']:10} conf={d['confidence']:.2f} sev={d['severity']:.2f} {d['reason']}")
            out.write(json.dumps({**it, **d}) + "\n")


def _test() -> None:
    def a(choice="a", confidence=0.9, score=1.0, noul=0.1):
        return {
            "bucket": {"choice": choice, "confidence": confidence, "probabilities": {}},
            "severity": {"score": score, "confidence": 0.9, "legend": {}, "probabilities": {}},
            "flag": {"noul": noul},
        }

    assert decide(a())["route"] == "a"
    assert decide(a(confidence=0.3))["reason"] == "low confidence"
    assert decide(a(score=1.95))["reason"] == "major severity"
    assert decide(a(noul=0.7))["flag"] is True
    print("ok")


if __name__ == "__main__":
    _test() if "--test" in sys.argv else run(sys.argv[1] if len(sys.argv) > 1 else "items.jsonl")
