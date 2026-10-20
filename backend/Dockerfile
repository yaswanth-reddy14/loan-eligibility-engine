FROM python:3.12.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace/backend:/workspace
WORKDIR /workspace
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend backend
COPY migrations migrations
COPY alembic.ini .
COPY frontend frontend
COPY n8n n8n
COPY scripts scripts
RUN useradd --create-home app
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
