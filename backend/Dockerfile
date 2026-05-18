FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias del sistema (psycopg/asyncpg compilan sin esto en Linux, pero bcrypt sí lo necesita)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

CMD ["uvicorn", "pokegrading.main:app", "--host", "0.0.0.0", "--port", "8000"]
