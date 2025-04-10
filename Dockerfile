# Use Python 3.9 as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV GITHUB_TOKEN=${GITHUB_TOKEN}
ENV GITHUB_ACCOUNT=${GITHUB_ACCOUNT}
ENV GITHUB_IS_ORGANIZATION=${GITHUB_IS_ORGANIZATION}
ENV SONAR_URL=${SONAR_URL}
ENV SONAR_TOKEN=${SONAR_TOKEN}
ENV NEXUS_URL=${NEXUS_URL}
ENV NEXUS_USERNAME=${NEXUS_USERNAME}
ENV NEXUS_PASSWORD=${NEXUS_PASSWORD}
ENV MONGO_URI=${MONGO_URI}

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run the application
CMD ["python", "org_repo_scanner.py"] 