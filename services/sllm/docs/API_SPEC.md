# sLLM 장애 로그 분석 API 스펙

## 개요

온프레미스 sLLM(Ollama + `qwen2.5:7b`)을 이용해 Kubernetes 장애 로그를 분석하고, 구조화된 JSON(장애 유형/원인/점검 항목/조치 항목)으로 반환하는 FastAPI 서비스입니다.

- 모델 호출: `http://localhost:11434/api/generate` (Ollama REST API, `format: "json"` 모드)
- 구현: [app/main.py](../app/main.py)

## 엔드포인트

### POST /analyze

K8s 장애 로그 텍스트를 받아 분석 결과를 JSON으로 반환합니다.

**요청**

```json
{
  "log_text": "2026-07-09T10:23:14Z [Warning] Pod payment-service-7d8f9c-x2k1p Container payment-api\nReason: OOMKilled\nExit Code: 137\n..."
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `log_text` | string | Y | 분석할 K8s 장애 로그 원문 |

**응답 (200, 정상 케이스)**

```json
{
  "failure_type": "OOMKilled",
  "root_cause": "Java heap space 부족으로 인해 OutOfMemoryError 발생",
  "checks": [
    "Java Heap Size 설정 확인",
    "메모리 사용량 모니터링 확인",
    "GC pause 시간 점검"
  ],
  "actions": [
    "Heap Size를 증가시켜 주기",
    "필요한 경우 메모리를 늘려주기"
  ],
  "degraded": false
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `failure_type` | string | 아래 [failure_type enum 목록](#failure_type-enum-목록) 중 하나 |
| `root_cause` | string | 추정 원인 (한국어, 기술 고유명사는 원문 유지) |
| `checks` | string[] | 점검해야 할 항목 목록 |
| `actions` | string[] | 권장 조치 항목 목록 |
| `degraded` | boolean | `true`면 일부 필드가 자동 폴백 처리됨 (아래 [degraded 케이스](#degraded-케이스) 참고) |

**응답 (200, degraded 케이스)**

모델 응답에 한자(CJK)나 코드성 패턴(`="`, `$변수` 등)이 감지되면 서버가 내부적으로 1회 재시도합니다. 재시도 후에도 문제가 남아있는 필드는 개별적으로 플레이스홀더로 대체되고, `degraded: true`가 함께 반환됩니다 (502로 실패시키지 않고 부분 성공으로 처리).

```json
{
  "failure_type": "DBConnectionFailure",
  "root_cause": "분석 실패 - 원본 로그 직접 확인 필요",
  "checks": [
    "PostgreSQL 서버 상태 확인",
    "커넥션 풀 설정 확인"
  ],
  "actions": [
    "데이터베이스 연결 수 늘리기",
    "커넥션 풀 관련 로그 검토"
  ],
  "degraded": true
}
```

- `failure_type`은 항상 1차 응답의 값을 그대로 유지합니다 (지금까지 실패율 0%로 확인됨).
- `root_cause`가 오염됐던 경우 `"분석 실패 - 원본 로그 직접 확인 필요"`로 대체됩니다.
- `checks`/`actions`는 **오염된 항목만 개별적으로** `"자동 분석 실패 - 수동 확인 필요"`로 대체되고, 문제 없는 항목은 그대로 유지됩니다.
- 폴백이 발동할 때마다 서버 로그(`logger.warning`)에 발동 횟수와 1차/재시도 응답 전체가 기록됩니다.

### GET /health

헬스체크 엔드포인트.

**응답 (200)**

```json
{ "status": "ok" }
```

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama REST API 엔드포인트 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 사용할 Ollama 모델명 |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Ollama 응답 대기 타임아웃(초) |

### Loki 폴러 (app/poller.py)

Loki에서 장애 로그를 주기적으로 조회해 `/analyze`로 자동 전달하는 백그라운드 폴러의 환경변수입니다. 실행: `python -m app.poller`

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LOKI_URL` | `http://localhost:3100` | Loki 서버 주소 |
| `LOKI_QUERY` | `{cluster=~".+"}` | Loki에 보낼 LogQL 쿼리 (키워드 필터링은 애플리케이션 코드에서 별도 수행) |
| `LOKI_MODE` | `mock` | `mock`(Loki 서버 없이 개발용 mock 응답 사용) 또는 `live`(실제 Loki `GET /loki/api/v1/query_range` 호출) |
| `LOKI_TIMEOUT_SECONDS` | `10` | Loki 요청 타임아웃(초) |
| `POLL_INTERVAL_SECONDS` | `30` | 폴링 주기(초) — 이 간격으로 `poll_once()`를 반복 실행 |
| `QUERY_WINDOW_SECONDS` | `300` | 매 폴링 시 조회할 Loki 쿼리 조회 윈도우(초), 즉 "최근 N초" 범위. 폴링 주기보다 넉넉하게 잡아 사이클 지연에도 로그 누락이 없도록 하며, 중복 조회분은 타임스탬프 워터마크로 걸러냄 |
| `ANALYZE_API_URL` | `http://localhost:8000/analyze` | 새로 감지된 장애 로그를 전달할 `/analyze` 엔드포인트 주소 |
| `ANALYZE_TIMEOUT_SECONDS` | `120` | `/analyze` 호출 타임아웃(초) |

**필터링 키워드**: `error`, `warning`, `oomkilled`, `crashloopbackoff` (대소문자 무관). 이 중 하나라도 포함된 로그 라인만 `/analyze`로 전달됩니다.

**에러 처리**: Loki 연결 실패/타임아웃/비정상 상태코드/응답 파싱 실패는 모두 해당 폴링 사이클만 건너뛰고 다음 사이클에서 자동으로 재시도합니다. `/analyze` 호출 실패(503/504/502)는 해당 로그 건만 건너뛰고 나머지 로그는 계속 처리합니다. 두 경우 모두 폴링 루프 자체는 죽지 않습니다.

## failure_type enum 목록

`failure_type`은 아래 9개 값 중 하나만 허용되도록 프롬프트로 강제됩니다. 로그가 어느 항목과도 명확히 일치하지 않으면 `Unknown`을 반환합니다.

- `OOMKilled`
- `CrashLoopBackOff`
- `ImagePullBackOff`
- `DBConnectionFailure`
- `LivenessProbeFailure`
- `DiskPressure`
- `NetworkTimeout`
- `ConfigurationError`
- `Unknown`

## 에러 응답

| 상태 코드 | 발생 조건 | 예시 |
|---|---|---|
| `503` | Ollama 서버에 연결할 수 없음 (프로세스 다운 등) | `{"detail":"Ollama 서버에 연결할 수 없습니다."}` |
| `504` | Ollama 응답이 `OLLAMA_TIMEOUT_SECONDS` 내에 오지 않음 | `{"detail":"Ollama 응답 시간 초과."}` |
| `502` | 모델이 유효한 JSON(`AnalyzeResponse` 스키마)을 반환하지 못함 | `{"detail":"모델 출력이 기대한 JSON 형식이 아닙니다: ..."}` |
| `200` + `degraded: true` | 재시도 후에도 checks/actions/root_cause에 오염된 값이 남아있음 (에러가 아닌 부분 성공으로 처리) | 위 [degraded 케이스](#degraded-케이스) 참고 |

503/504는 시스템 장애(Ollama 다운/과부하)로 간주해 명확히 실패 처리하고, 모델 출력 품질 문제(한자/코드 혼입)는 재시도 + 부분 폴백으로 최대한 200을 유지하도록 설계했습니다.

## 알려진 한계

- qwen2.5:7b는 드물게(테스트 기준 약 15~20% 수준) `checks`/`actions`에 로그 내용과 무관한 일반론이나 어색한 표현을 포함시킵니다. 정규식 기반 검증(한자, 셸 변수/코드 패턴)은 이 중 일부만 잡아내며, "로그와 무관한 내용" 자체를 판별하는 검증은 아직 없습니다.
- 모델이 유효한 JSON을 반환하지 못해 `502`로 실패하는 경우가 드물게 있습니다 (VM 벤치마크 35회 기준 **5.71%, 2/35** — [analyze_benchmark_vm.csv](analyze_benchmark_vm.csv) 참고). 이는 위의 `checks`/`actions` 오염(한자·어색한 일반론, 15~20%)과는 별개의 실패 유형으로, 한자/코드 패턴 감지 후 재시도하는 `degraded` 로직과 무관하게 **첫 호출의 모델 출력 자체가 JSON 파싱에 실패**한 경우입니다. 현재 `/analyze`는 이 경우 재시도 없이 즉시 502를 반환하므로, 클라이언트(예: `app/poller.py`) 쪽에서 502 발생 시 해당 로그 건에 한해 재시도하는 방어 로직을 갖추는 것을 권장합니다.
- 따라서 이 API의 출력은 **SRE의 최종 판단을 대체하지 않고 보조하는 용도**로 설계되었습니다. 특히 `degraded: true`가 아니더라도 내용의 최종 검증은 사람이 하는 것을 전제로 합니다.

## 평균 응답 시간

**실제 운영 환경(온프레 CPU 전용) 기준** — `qwen2.5:7b`, CPU-only 10회 실측(`CUDA_VISIBLE_DEVICES=-1`, `OLLAMA_LLM_LIBRARY=cpu`로 GPU를 강제로 숨기고 `ollama ps`로 100% CPU 확인 후 측정):

- 정상 케이스 기준 **평균 22.3초** (범위 15.0초~38.3초)
- 재시도가 발생하는 경우 2배 가까이(최대 1분 내외) 소요될 수 있음
- Ollama 다운 시 503은 즉시(약 2~3초 내), 타임아웃 시 504는 `OLLAMA_TIMEOUT_SECONDS` 설정값만큼 대기 후 반환

> **각주(로컬 개발 환경 기준, 실제 운영과 다름)**: 로컬 개발 머신은 RTX 3060 GPU가 있어 Ollama가 별도 설정 없이는 자동으로 GPU를 사용합니다. 이 경우 응답 시간은 약 4~8초로 CPU 대비 3~5배 빠르지만, **온프레 운영 서버에는 GPU가 없으므로 이 수치는 실제 운영 성능을 대표하지 않습니다.** 로컬에서 성능을 체감할 때는 이 차이를 감안해야 합니다.

### VM 벤치마크 (실측)

**환경**: VMware Ubuntu VM (4코어 CPU, RAM 15Gi), `qwen2.5:7b`, CPU-only.

7종 장애 유형(`OOMKilled`, `CrashLoopBackOff`, `ImagePullBackOff`, `DBConnectionFailure`, `LivenessProbeFailure`, `DiskPressure`, `NetworkTimeout`) 각 5회씩 총 **35회** `/analyze` 실측. 원본 데이터: [analyze_benchmark_vm.csv](analyze_benchmark_vm.csv) (측정 스크립트: [run_benchmark.py](../test_artifacts/run_benchmark.py)).

**전체 평균 37.10초 (범위 12.85초~91.38초)**

| 장애 유형 | 평균 응답시간(초) | 범위(초) |
|---|---|---|
| OOMKilled | 50.71 | 29.40 ~ 91.38 |
| CrashLoopBackOff | 41.83 | 25.99 ~ 66.06 |
| ImagePullBackOff | 38.43 | 23.35 ~ 68.64 |
| DBConnectionFailure | 47.74 | 31.90 ~ 70.91 |
| LivenessProbeFailure | 43.10 | 34.20 ~ 57.58 |
| DiskPressure | 17.95 | 12.85 ~ 22.60 |
| NetworkTimeout | 19.95 | 15.51 ~ 30.41 |

- `degraded: true` 발생률: **5.71% (2/35)**
- `502`(모델 출력 JSON 파싱 실패) 발생률: **5.71% (2/35)** — [알려진 한계](#알려진-한계) 참고
- `failure_type` 오분류: **0건** (502로 호출 자체가 실패한 2건을 제외한 33건 모두 기대한 유형과 일치)

### 로컬 vs VM 비교

| 항목 | 로컬 (CPU-only 강제, RTX 3060 머신) | VM (VMware Ubuntu, 4코어/15Gi) |
|---|---|---|
| 표본 | 10회 (`OOMKilled`·`CrashLoopBackOff` 각 5회) | 35회 (7종 장애유형 각 5회) |
| 평균 응답시간 | 22.3초 | 37.10초 |
| 범위 | 15.0 ~ 38.3초 | 12.85 ~ 91.38초 |
| degraded 발생률 | 별도 미측정 | 5.71% (2/35) |
| 502(JSON 파싱 실패) 발생률 | 별도 미측정 | 5.71% (2/35) |

VM 평균이 로컬보다 약 1.7배 높고 최댓값 편차(최대 91.38초)도 더 큽니다. 두 환경 모두 GPU 없이 CPU만 사용했지만, VM은 4코어/15Gi로 리소스가 더 제한적이어서 실제 온프레 운영 서버 성능에 더 가까운 참고치로 볼 수 있습니다.

### 알려진 제약: 폴링 주기와 분석 소요 시간의 근접/역전

`app/poller.py`의 `POLL_INTERVAL_SECONDS` 기본값(30초)은 CPU-only 환경의 평균 분석 소요 시간(22.3초, 최대 38.3초)과 근접하거나 역전될 수 있습니다. 즉 한 로그의 `/analyze` 처리가 끝나기 전에 다음 폴링 사이클이 시작될 수 있어, 폴링 주기 동안 여러 건의 장애 로그가 감지되면 `/analyze` 호출이 누적되어 지연이 커질 수 있습니다. 운영 배포 시에는 `POLL_INTERVAL_SECONDS`를 분석 소요 시간보다 충분히 크게 잡거나(예: 60초 이상), `/analyze` 호출을 큐잉/동시성 제한하는 구조를 함께 고려해야 합니다.

## 모델 비교: qwen2.5:3b vs qwen2.5:7b (모델 선택 근거)

동일한 프롬프트(한국어 강제 + failure_type enum 강제 + 고유명사 인용 규칙)로 CPU-only 환경에서 OOMKilled/CrashLoopBackOff 로그 각 5회씩(모델당 10회, 단일 호출·재시도 없음) 비교한 결과입니다.

| 항목 | qwen2.5:3b | qwen2.5:7b |
|---|---|---|
| 평균 응답 시간 | 10.6초 (6.7~18.8초) | 22.3초 (15.0~38.3초) |
| 한자(CJK) 혼입률 | 3/10 (30%) | 2/10 (20%) |
| **완전 영어 이탈** (한국어 강제 무시) | **2/10 (20%)** — CrashLoopBackOff 5회 중 2회 응답 전체가 영어 | 0/10 |
| **failure_type 오분류율** | **2/5 (40%)** — CrashLoopBackOff 로그를 `LivenessProbeFailure`로 잘못 분류 (enum 값 자체는 유효해서 스키마 검증은 통과) | 0/10 |

**결론**: 3B는 7B보다 약 2.1배 빠르지만, 한국어 강제 지시를 통째로 무시하거나(완전 영어 응답) 장애 유형 자체를 잘못 분류하는 근본적인 품질 문제가 있습니다. 특히 failure_type 오분류는 정규식 기반 검증(한자/코드 패턴)으로 걸러낼 수 없는 문제입니다. 응답 속도보다 분류 정확도가 우선이라고 판단해 **최종적으로 qwen2.5:7b를 선택**했습니다.
