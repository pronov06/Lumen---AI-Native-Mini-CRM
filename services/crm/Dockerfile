FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

EXPOSE 8000

# Single worker: the in-process send worker and the per-communication locks
# assume one process. Scale out with multiple replicas behind Postgres + Redis,
# where the row-level FOR UPDATE lock takes over from the in-process lock.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
