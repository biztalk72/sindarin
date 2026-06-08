# Generic worker image. Pass WORKER to select the package, e.g.:
#   docker build -f infra/docker/worker.Dockerfile --build-arg WORKER=ocr_worker -t worker-ocr .
# OCR/VL images additionally install PaddleOCR system deps (added per-worker as needed).
FROM python:3.12-slim
ARG WORKER=ocr_worker
ENV PYTHONUNBUFFERED=1 WORKER=${WORKER}
WORKDIR /srv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
COPY packages ./packages
COPY workers ./workers
RUN uv sync --no-dev

# Each worker package exposes a process()/index() entrypoint; the runner wiring (queue
# consumer) is implemented per worker (PRD2 §3, GB10 concurrency/memory caps).
CMD ["sh", "-c", "echo \"worker image: ${WORKER} (entrypoint TODO)\" && sleep infinity"]
