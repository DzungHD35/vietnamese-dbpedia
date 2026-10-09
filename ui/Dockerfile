# Build context = gốc repo:  docker build -f ui/Dockerfile .
FROM node:22-slim AS web
WORKDIR /web
COPY ui/web/package.json ui/web/package-lock.json ./
RUN npm ci
COPY ui/web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=web /web/dist ui/web/dist
EXPOSE 8000
CMD ["python", "-m", "ui.api", "--host", "0.0.0.0", "--port", "8000"]
