FROM python:3.11-slim

WORKDIR /app

# Install system deps for optional packages (not strictly required but helpful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV FLASK_APP=src.main
EXPOSE 1212

# The web subcommand defaults to --host 127.0.0.1 --port 1212. Inside a
# container 127.0.0.1 is the container's own loopback, which a published
# port can never reach, and EXPOSE said 5000 while the app listened on 1212.
CMD ["python", "-m", "src.main", "web", "--host", "0.0.0.0", "--port", "1212"]
