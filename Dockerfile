# ReceiptScanner API Backend Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for OpenCV and Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and samples
COPY src/ ./src/
COPY samples/ ./samples/
COPY run.py .

EXPOSE 5000

ENV PYTHONUNBUFFERED=1

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5000"]
