#!/usr/bin/env python3
"""Confidence-gated ticket triage on a local jev server (open-jev, POST /v1/systemone).

One request per ticket -> department (choice), severity (score), wants_refund (noul).
Confident + not major -> auto-route to the department. Otherwise -> human review queue.
No decoding, no JSON parsing of model output: jev returns probabilities directly.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("TYPESAFE_API_KEY", "local")
THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.6"))  # ponytail: tune per model; zero-shot Qwen/Gemma is over-confident, a trained head lets you raise this
MAJOR = 1.9  # severity score (0..2) at or above which a human must look

QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which department handles this ticket?",
        "criteria": {
            "returns": "Wrong, damaged or unwanted items; exchanges",
            "shipping": "Delivery delays, tracking, lost packages",
            "billing": "Charges, invoices, refunds to card",
            "technical": "App or website bugs, login problems, crashes",
            "sales": "Pre-purchase questions, pricing, availability",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How severe is the customer's problem?",
        "criteria": [
            "minor: a question or a cosmetic issue",
            "moderate: wrong or broken item, late or lost delivery, login trouble, duplicate charge",
            "major: physical injury risk, fire, or money already lost",
        ],
    },
    "wants_refund": {
        "type": "noul",
        "instructions": "Is the customer explicitly asking for money back?",
    },
}


def judge(text: str) -> dict:
    body = json.dumps({"state": text, "model": "jev-latest", "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/systemone",
        body,
        {"content-type": "application/json", "authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["answers"]


def decide(answers: dict, threshold: float = THRESHOLD) -> dict:
    dept, sev, refund = answers["department"], answers["severity"], answers["wants_refund"]
    d = {
        "department": dept["choice"],
        "confidence": round(dept["confidence"], 2),
        "severity": round(sev["score"], 2),
        "wants_refund": refund["noul"] >= 0.5,
    }
    if dept["confidence"] < threshold:
        d["route"], d["reason"] = "human", "low confidence"
    elif sev["score"] >= MAJOR:
        d["route"], d["reason"] = "human", "major severity"
    else:
        d["route"], d["reason"] = dept["choice"], ""
    return d


def main(path: str) -> None:
    tickets = [json.loads(l) for l in open(path) if l.strip()]
    print(f"{'id':6} {'route':9} {'dept':9} {'conf':>5} {'sev':>4} {'refund':6} reason")
    with open("decisions.jsonl", "w") as out:
        for t in tickets:
            try:
                d = decide(judge(t["text"]))
            except urllib.error.URLError as e:
                sys.exit(f"cannot reach jev at {BASE_URL} ({e.reason}). Run `make serve` first.")
            print(f"{t['id']:6} {d['route']:9} {d['department']:9} {d['confidence']:5.2f} "
                  f"{d['severity']:4.2f} {str(d['wants_refund']):6} {d['reason']}")
            out.write(json.dumps({**t, **d}) + "\n")
    print("-> decisions.jsonl")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tickets.jsonl")
