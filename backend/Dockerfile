FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN groupadd --system shortlist && useradd --system --gid shortlist --home-dir /app --no-create-home shortlist
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY start.sh ./start.sh
RUN chmod 0555 ./start.sh && chown -R shortlist:shortlist /app

USER shortlist
EXPOSE 8000
CMD ["./start.sh"]
