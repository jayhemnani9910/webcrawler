# This file used to contain two complete Dockerfiles stacked, which Docker reads
# as an accidental multi-stage build and silently keeps only the last stage. The
# surviving stage EXPOSEd 16000 while app.py's hardcoded app.run() bound 8080.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/
VOLUME ["/data/ots"]
# app.py honours PORT and defaults to 8080, which docker-compose.integration.yml
# publishes. docker-compose.prod.yml sets PORT=16000 and publishes that.
EXPOSE 8080
CMD ["python", "app.py"]
