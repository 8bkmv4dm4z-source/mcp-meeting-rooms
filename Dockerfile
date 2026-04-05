FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install -e .

COPY scripts/ scripts/
COPY start.sh .

RUN chmod +x start.sh

ENV MR_TRANSPORT=sse
ENV MR_HOST=0.0.0.0

CMD ["./start.sh"]
