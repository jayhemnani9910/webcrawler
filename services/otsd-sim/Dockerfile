FROM python:3.11-slim
WORKDIR /app
COPY app.py /app/app.py
RUN pip install flask
VOLUME /data
EXPOSE 8080
CMD ["python", "app.py"]
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/
VOLUME ["/data/ots"]
EXPOSE 16000
CMD ["python", "app.py"]
