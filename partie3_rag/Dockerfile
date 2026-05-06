FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["uvicorn", "api.rag_api:app", "--host", "0.0.0.0", "--port", "8002"]