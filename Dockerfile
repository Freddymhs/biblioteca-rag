FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache — only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

# Uvicorn with 2 workers for production
# For dev: override with `uvicorn main:app --reload`
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
