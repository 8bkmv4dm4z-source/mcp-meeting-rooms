FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install .

COPY scripts/ scripts/
COPY start.sh .

RUN chmod +x start.sh

ENV MR_TRANSPORT=streamable-http
ENV MR_HOST=0.0.0.0
ENV PORT=8000
ENV MR_DB_PATH=/data/meeting_rooms.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["./start.sh"]
