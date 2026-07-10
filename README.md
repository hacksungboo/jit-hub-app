# JIT-Hub App

> Just-In-Time Hybrid DR Platform on Kubernetes

JIT-Hub App 저장소는 JIT-Hub 프로젝트의 애플리케이션 계층을 관리합니다.  
FastAPI 기반 마이크로서비스, Nginx 리버스 프록시, 경량 Docker 이미지를 통해 하이브리드 DR 아키텍처에서 동작하는 웹 API를 제공합니다.

## 주요 기능

- FastAPI 기반 API 제공 서비스
- 온프레미스 PostgreSQL 연동 서비스 로직
- Nginx 리버스 프록시 및 라우팅 구성
- 멀티 스테이지 Dockerfile을 활용한 경량 컨테이너 이미지
- GitHub Actions 기반 빌드·테스트·이미지 푸시

## 아키텍처

동일한 애플리케이션 이미지는 다음 환경에서 실행되도록 설계되었습니다.

- AWS EKS A 리전 – 메인 서비스
- 온프레미스 Kubernetes – Standby 서비스
- AWS EKS B 리전 – DR 시나리오용 JIT 클러스터

메인 PostgreSQL 데이터베이스는 온프레미스에 위치합니다.

## 시작하기

로컬 실행:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docker 실행:

```bash
docker build -t jit-hub-app:dev .
docker run -p 8000:8000 jit-hub-app:dev
```

## 저장소 구조 (예시)

```text
services/
  inventory-api/
  orders-api/
  customers-api/
gateway/
  nginx/
shared/
  config/
  db/
  utils/
.github/
  workflows/
```

## 관련 저장소

- 인프라 및 GitOps 구성: `jit-hub-infra`