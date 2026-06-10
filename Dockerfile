FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tools ./tools

ENV CLIPNEST_DATA_DIR=/data
ENV CLIPNEST_DOWNLOAD_DIR=/downloads

EXPOSE 8080

CMD ["python", "-m", "app.container_process"]
