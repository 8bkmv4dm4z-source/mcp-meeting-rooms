FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install -e .

COPY scripts/ scripts/

CMD python scripts/seed.py --schema-only && python -m meeting_rooms.server
