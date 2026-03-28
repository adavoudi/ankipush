FROM python:3.11-slim
RUN pip install --no-cache-dir anki
ENV SYNC_HOST=0.0.0.0
ENV SYNC_PORT=8080
CMD ["python", "-m", "anki.syncserver"]
