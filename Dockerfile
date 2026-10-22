FROM python:3.15.1-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY run.py .
COPY config.env.example config.env

# Create data directory
RUN mkdir -p data

EXPOSE 5050

CMD ["python", "run.py"]
