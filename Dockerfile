# Use official lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing pyc files to disk and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for ReportLab / Pillow / Matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure generated output directories exist
RUN mkdir -p generated/invoices generated/reports

# Run seed script on startup then launch Telegram bot
CMD ["sh", "-c", "python app/main.py --seed && python app/main.py --bot"]
