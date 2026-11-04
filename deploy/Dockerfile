# Public StaffGalaxy: FastAPI serves /api from the SQLite store and the Vite build.
# Build from the repository root:  docker build -f deploy/Dockerfile -t staffgalaxy .
# The store is not baked in: mount it at /data/staff_galaxy.sqlite (see compose.yml).

FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY staff_galaxy/ staff_galaxy/
RUN pip install --no-cache-dir . && useradd --system --uid 10001 app
COPY --from=frontend /src/frontend/dist /app/static

ENV STAFF_GALAXY_STORE=/data/staff_galaxy.sqlite \
    STAFF_GALAXY_STATIC=/app/static \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "staff_galaxy.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
