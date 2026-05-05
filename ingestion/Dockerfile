FROM python:3.11-slim

# Install necessary build tools for confluent-kafka (requires librdkafka)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libc6-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire ingestion folder
COPY . /app/ingestion/

# Set env 
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "ingestion.main"]
