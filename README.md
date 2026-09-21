# jev-local-sample

로컬 jev([open-jev](https://github.com/daseinlabs/open-jev))로 고객 문의를 **confidence 게이트 트리아지**하는 예제.
기준 글: [로컬에서 jev를 돌려보자](https://blog.naver.com/pjt3591oo/224416967300)

## 왜 이 케이스인가

jev는 텍스트를 생성하지 않는다. 미리 정한 선택지의 **확률과 confidence만** 1회 forward pass(~90ms)로 돌려준다.
그래서 생성형 LLM이 과한 자리 — 대량·반복·저지연 분류 — 에서 가장 잘 맞고, confidence가 있어서
"확신 있으면 자동, 아니면 사람" 분기를 코드 한 줄로 만들 수 있다. 로컬이라 비용 0, 데이터 외부 유출 없음.

티켓 1건 → 질문 3개(choice/score/noul) → 라우팅:

| 조건 | 라우팅 |
|---|---|
| department confidence < 0.6 | `human` (low confidence) |
| severity ≥ 1.9 (0~2) | `human` (major severity) |
| 그 외 | 해당 부서로 자동 |

`wants_refund`는 플래그로만 붙는다.

## 실행

Apple silicon 전용(MLX). `uv`, `hf` CLI 필요.

```bash
make setup    # open-jev clone + venv + gemma-3-4b-it-4bit 다운로드 (Qwen: make setup MODEL=models/Qwen2.5-1.5B-Instruct-4bit HF_REPO=mlx-community/Qwen2.5-1.5B-Instruct-4bit)
make serve    # :8000 에서 jev 서버 기동 (다른 터미널)
make triage   # tickets.jsonl 판정 → 표 출력 + decisions.jsonl
make test     # 라우팅 규칙 단위 테스트 (서버 불필요)
```

환경변수: `TYPESAFE_BASE_URL`(기본 `http://127.0.0.1:8000`), `TYPESAFE_API_KEY`, `CONFIDENCE_THRESHOLD`(기본 0.6).
`TYPESAFE_BASE_URL`을 실제 TypeSafe 엔드포인트로 바꾸면 코드 수정 없이 진짜 jev로 전환된다.

## 파일

- `triage.py` — stdlib만 사용. `judge()`가 `/v1/systemone` 호출, `decide()`가 라우팅 규칙.
- `tickets.jsonl` — 샘플 티켓 10건(모호한 것, 복합 이슈, 안전 문제 포함).
- `test_triage.py` — `decide()` 검증.
- `blog/` — 이 예제를 정리한 [블로그 초안](blog/jev-triage-draft.md) (네이버 붙여넣기용 [HTML](blog/jev-triage-draft.html)).

## 실행 결과 (gemma-3-4b-it-4bit, 10건 ≈ 18초)

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

자동 처리 8/10. 사람 검토는 히터 발연·콘센트 녹음(T-005)과 빈 티켓 "hi"(T-007)뿐.

## 튜닝 노트

레버는 임계값이 아니라 **criteria 문구**다. Gemma-3-4B는 부정적 티켓을 거의 전부 major(p≈0.98)로 밀어
`MAJOR`를 1.5→1.9로 올려도 결과가 안 바뀌었다. `moderate`에 실제 케이스(늦은 배송, 파손, 로그인 문제, 중복 결제)를
명시적으로 열거하자 그 케이스들이 1.0으로 내려가고 히터 발연(T-005)만 major로 남았다. jev는 선택지 설명을 state와 직접
매칭하므로, 분류가 흔들리면 설명에 예시를 넣는 것이 첫 번째 조치다.

## 한계

zero-shot 소형 모델의 확률은 보정되지 않았다(open-jev README 참고: over-confident). 임계값은 모델별로 튜닝하고,
정확한 confidence가 필요하면 open-jev의 `make features/train`으로 라벨 데이터에 head를 학습시킨다.
