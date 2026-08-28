FROM python:3.11-slim

WORKDIR /app

# Install system deps for optional packages (not strictly required but helpful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# The container ran as root, so every file it wrote, including the database and
# anything under keys/, was created root-owned. Create an unprivileged user and
# give it the app directory and the data directory the compose files mount.
RUN useradd --system --create-home --shell /usr/sbin/nologin watcher \
    && mkdir -p /var/lib/website-watcher \
    && chown -R watcher:watcher /app /var/lib/website-watcher
USER watcher

ENV FLASK_APP=src.main
EXPOSE 1212

# The web subcommand defaults to --host 127.0.0.1 --port 1212. Inside a
# container 127.0.0.1 is the container's own loopback, which a published
# port can never reach, and EXPOSE said 5000 while the app listened on 1212.
CMD ["python", "-m", "src.main", "web", "--host", "0.0.0.0", "--port", "1212"]
