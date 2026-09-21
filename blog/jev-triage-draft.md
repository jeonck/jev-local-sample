# 로컬 jev로 고객 문의 자동 분류하기 — 확신 없으면 사람에게 넘기는 트리아지

로컬에서 띄운 jev(open-jev)에 티켓 한 건당 HTTP 요청 하나를 보내면 부서·심각도·환불요구를 확률로 돌려줍니다. 그 확률에 "확신도 0.6 미만이거나 심각도 major면 사람 검토, 아니면 부서로 자동 전달" 규칙 하나를 얹어 10건 중 8건을 자동 처리하는 예제를 만들었습니다. 코드는 stdlib만 쓰고 60줄입니다.

- 코드: https://github.com/jeonck/jev-local-sample
- 참고한 글: 멍개님의 "로컬에서 jev를 돌려보자" (https://blog.naver.com/pjt3591oo/224416967300)

## jev가 잘 맞는 자리는 어디인가

지난 글들에서 본 것처럼 jev는 텍스트를 생성하지 않습니다. 미리 정해둔 선택지(choice), 단계(score), 예/아니오(noul)에 대해 확률과 confidence만 돌려줍니다. 디코딩이 없으니 한 질문에 수십 ms, JSON 파싱 실패도 없고, 환각도 없습니다.

그래서 생성형 LLM을 쓰기엔 과한 자리 — 대량으로 반복되는 분류·라우팅 — 가 jev의 자리입니다. 그리고 confidence가 같이 오기 때문에 "확신 있으면 자동, 아니면 사람" 분기를 코드 한 줄로 만들 수 있습니다. 로컬이면 비용 0, 고객 데이터가 밖으로 나가지도 않습니다.

이 조건을 모두 만족하는 가장 흔한 업무가 고객 문의 트리아지라서 이걸로 잡았습니다.

## 설계: 질문 3개, 규칙 2개

티켓 본문을 state로 넣고 질문 세 개를 묶어 보냅니다.

| 질문 | 타입 | 내용 |
|---|---|---|
| department | choice | returns / shipping / billing / technical / sales 중 어디로 |
| severity | score | minor(0) / moderate(1) / major(2) |
| wants_refund | noul | 돈을 돌려달라고 명시했는가 |

라우팅 규칙은 둘뿐입니다.

- department의 confidence < 0.6 → `human` (low confidence)
- severity ≥ 1.9 → `human` (major severity)
- 그 외 → 해당 부서로 자동

wants_refund는 라우팅에 쓰지 않고 플래그로만 붙입니다.

## 코드

핵심은 두 함수입니다. `judge()`가 `/v1/systemone`을 호출하고 `decide()`가 규칙을 적용합니다.

```python
def judge(text: str) -> dict:
    body = json.dumps({"state": text, "model": "jev-latest", "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/systemone", body,
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
```

`BASE_URL`은 `TYPESAFE_BASE_URL` 환경변수에서 읽습니다. 로컬 open-jev 대신 진짜 TypeSafe 엔드포인트를 넣으면 코드 수정 없이 그대로 돌아갑니다.

## 실행

Apple silicon 전용(MLX)입니다. `uv`와 `hf` CLI가 있으면 됩니다.

```
$ make setup    # open-jev clone + venv + gemma-3-4b-it-4bit 다운로드
$ make serve    # :8000 에서 jev 서버 (다른 터미널)
$ make triage   # tickets.jsonl 10건 판정
```

open-jev 기본 모델은 google/gemma-3-4b-it인데 HF 로그인이 필요한 gated 모델입니다. mlx-community/gemma-3-4b-it-4bit는 로그인 없이 받아지고 MLX용으로 이미 변환되어 있어 이쪽을 썼습니다. 용량은 약 2.5GB, 로드 8초입니다.

## 결과

```
id     route     dept       conf  sev refund reason
T-001  returns   returns    1.00 1.00 False
T-002  shipping  shipping   1.00 1.04 False
T-003  billing   billing    1.00 1.00 True
T-004  technical technical  1.00 1.04 False
T-005  human     billing    0.93 2.00 True   major severity
T-006  shipping  shipping   1.00 0.01 False
T-007  human     returns    0.32 0.05 False  low confidence
T-008  billing   billing    1.00 1.01 False
T-009  technical technical  1.00 1.00 False
T-010  returns   returns    1.00 1.00 False
```

10건 중 8건 자동 처리. 사람에게 간 두 건은 "히터에서 연기가 나고 콘센트가 녹았다"(T-005)와 본문이 "hi" 한 단어인 티켓(T-007)입니다. 딱 사람이 봐야 할 것만 남았습니다. 10건에 약 18초, 질문 하나당 0.6초 정도입니다.

## 삽질 1: Qwen 1.5B는 부서를 못 가른다

처음엔 멍개님 글대로 Qwen2.5-1.5B-Instruct-4bit로 돌렸습니다. 5초 만에 끝나서 좋았는데 결과가 이랬습니다.

```
T-001  human     billing    0.46 1.03 False  low confidence   ← 사이즈 오배송인데 billing
T-006  billing   billing    0.66 1.20 False                   ← 배송 문의인데 billing
T-010  human     returns    0.53 1.00 False  low confidence
```

거의 모든 티켓이 billing으로 쏠리고 confidence도 0.5 근처에서 흔들립니다. 게이트 덕분에 애매한 건 사람에게 가긴 하지만 자동 처리율이 2/10이라 의미가 없습니다. Gemma 3 4B로 바꾸자 부서 판정이 10건 중 9건 타당해졌습니다(T-006 "캐나다 배송 되나요?"를 sales 대신 shipping으로 본 건 변명 가능한 수준).

## 삽질 2: 임계값을 올려도 안 바뀐다

Gemma로 바꾼 직후 결과는 사실 이랬습니다.

```
T-002  human     shipping   1.00 1.99   major severity   ← 배송 9일 지연
T-008  human     billing    1.00 2.00   major severity   ← 깨진 머그
T-009  human     technical  1.00 2.00   major severity   ← 로그인 잠김
```

부정적인 티켓은 전부 major로 밀어버립니다. 그래서 MAJOR 임계값을 1.5에서 1.9로 올렸는데 결과가 한 글자도 안 바뀌었습니다. T-002의 원시 확률을 찍어보니 `{"1": 0.016, "2": 0.984}` — 점수가 1.0 아니면 2.0으로 이분법적이라 임계값을 어디에 두든 같은 자리에서 잘립니다.

## 해결: 레버는 임계값이 아니라 criteria 문구

jev는 선택지 설명을 state와 직접 매칭합니다. 그러니 "어떤 케이스가 moderate인지"를 설명에 직접 써주면 됩니다.

바꾸기 전:

```
"moderate: wrong item, delay, or a blocked purchase",
"major: safety hazard, outage, or financial loss",
```

바꾼 후:

```
"moderate: wrong or broken item, late or lost delivery, login trouble, duplicate charge",
"major: physical injury risk, fire, or money already lost",
```

major만 좁혀서는 부족했고(T-002가 여전히 0.98로 major), moderate에 실제 케이스를 열거하자 T-002/T-008/T-009가 2.0에서 1.0으로 내려오고 히터 발연(T-005)만 major로 남았습니다. 위의 최종 결과가 이 상태입니다.

정리하면 jev에서 분류가 흔들릴 때 첫 번째로 손댈 곳은 임계값이 아니라 criteria 설명입니다. 예시를 넣는 게 가장 강한 레버였습니다.

## 남은 한계

zero-shot 확률은 보정된 값이 아닙니다. Gemma가 confidence 1.00을 남발하는 게 그 증거입니다. open-jev README도 같은 경고를 하고 있고, 정확한 confidence가 필요하면 `make features` / `make train`으로 라벨 데이터에 head를 학습시키라고 안내합니다. 이 예제에서는 criteria 문구 조정으로 충분했지만, 실제 운영이라면 그 단계가 필요할 겁니다.

전체 코드와 샘플 티켓, 테스트는 https://github.com/jeonck/jev-local-sample 에 있습니다.
