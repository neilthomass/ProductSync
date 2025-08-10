FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system .

# Copy application code
COPY . .

# Create models directory for NLP models
RUN mkdir -p models

# Download spaCy model
RUN python -m spacy download en_core_web_md

# Create non-root user
RUN useradd --create-home --shell /bin/bash productsync && \
    chown -R productsync:productsync /app
USER productsync

# Expose ports
EXPOSE 5000 5555

# Default command
CMD ["python", "main.py"] 