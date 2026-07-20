from fastapi import FastAPI, Request  # Request test 추가 
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi.responses import Response                              # keda 오토스케일리용 메트릭 수집
from prometheus_client import Counter, generate_latest, REGISTRY

from .database import engine
from .models import Base
from .seed import seed_tourist
from .routers import tourist
from .config import settings

# keda가 RPS 판단에 사용 할 요청 수 카운터 
REQUEST_COUNT = Counter(
    'http_requests_total',  # 메트릭 이름 (KEDA가 읽을 이름)
    'Total HTTP requests',   # 설명
    ['method', 'endpoint', 'status'],  # 추적할 정보
    registry=REGISTRY
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_tourist()
    yield


app = FastAPI(title="JIT-Hub Tourist Service", lifespan=lifespan)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    """모든 HTTP 요청을 Prometheus 메트릭에 기록"""
    response = await call_next(request)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tourist.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tourist",
        "location": settings.jithub_location,
        "timestamp": datetime.now(timezone.utc),
    }

# 수집된 값을 prometheus 텍스트 형식으로 반환
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),  # Prometheus 형식으로 변환
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )