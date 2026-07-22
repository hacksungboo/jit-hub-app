FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/sllm/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app
ENV PATH=/root/.local/bin:$PATH
COPY --from=builder /root/.local /root/.local
COPY services/sllm/app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
