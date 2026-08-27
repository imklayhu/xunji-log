# Stage 1: build frontend
FROM node:22-alpine AS web-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: Python API + static
FROM python:3.12-slim
WORKDIR /app

COPY server/requirements.txt ./server/
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r server/requirements.txt

COPY server/ ./server/
COPY scripts/ ./scripts/
COPY data/ ./data/

COPY --from=web-build /app/web/dist ./web/dist

ENV DATA_DIR=/app/data
ENV STATIC_DIR=/app/web/dist
ENV TZ=Asia/Shanghai

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
