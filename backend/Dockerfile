# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=120
WORKDIR /build
# Some hosts have broken IPv6 routes to PyPI; prefer IPv4 so pip does not stall.
RUN echo "precedence ::ffff:0:0/96 100" >> /etc/gai.conf
COPY requirements/ requirements/
ARG REQUIREMENTS=requirements/base.txt
RUN --mount=type=cache,target=/root/.cache/pip pip wheel --wheel-dir /wheels -r ${REQUIREMENTS}

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Outbound calls (GitHub, LeetCode) hit the same IPv6 issue as pip on some hosts; prefer IPv4.
RUN echo "precedence ::ffff:0:0/96 100" >> /etc/gai.conf
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index /wheels/* && rm -rf /wheels
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
