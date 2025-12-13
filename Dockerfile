FROM python:3.11-slim

WORKDIR /app

# Install system deps for optional packages (not strictly required but helpful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV FLASK_APP=src.main
EXPOSE 5000

CMD ["python", "-m", "src.main", "web"]
