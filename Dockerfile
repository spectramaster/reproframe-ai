FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    REPROFRAME_MODE=fixture \
    REPROFRAME_ARTIFACT_DIR=/home/user/app/artifacts/runs

RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml README.md LICENSE ./
COPY --chown=user:user src ./src

RUN python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && python -m pip install --no-cache-dir ".[backblaze]"
RUN mkdir -p /home/user/app/artifacts/runs && chown -R user:user /home/user/app/artifacts

USER user
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3)"

CMD ["uvicorn", "reproframe.api:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
