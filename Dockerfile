FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard.py .
COPY main.py .
COPY templates/ templates/

# Create empty data files
RUN echo '[]' > processed_emails.json && \
    echo '{}' > pending_articles.json && \
    echo '[]' > published_articles.json

EXPOSE 5050

CMD ["python", "dashboard.py"]
