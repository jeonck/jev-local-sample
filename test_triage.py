from triage import decide


def answers(choice="returns", confidence=0.9, score=1.0, noul=0.1):
    return {
        "department": {"type": "choice", "choice": choice, "confidence": confidence, "probabilities": {}},
        "severity": {"type": "score", "score": score, "confidence": 0.9, "legend": {}, "probabilities": {}},
        "wants_refund": {"type": "noul", "noul": noul},
    }


assert decide(answers())["route"] == "returns"
assert decide(answers(confidence=0.3))["reason"] == "low confidence"
assert decide(answers(score=1.95))["reason"] == "major severity"
assert decide(answers(noul=0.7))["wants_refund"] is True
assert decide(answers(confidence=0.5), threshold=0.4)["route"] == "returns"
print("ok")
