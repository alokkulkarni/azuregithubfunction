# Use Python 3.9 as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GITHUB_TOKEN=${GITHUB_TOKEN}
ENV GITHUB_ORG=${GITHUB_ORG}
ENV SONAR_URL=${SONAR_URL}
ENV SONAR_TOKEN=${SONAR_TOKEN}
ENV NEXUS_URL=${NEXUS_URL}
ENV NEXUS_USERNAME=${NEXUS_USERNAME}
ENV NEXUS_PASSWORD=${NEXUS_PASSWORD}
ENV MONGO_URI=${MONGO_URI}

# Create directory for Excel files
RUN mkdir -p /app/output

# Set entrypoint
ENTRYPOINT ["python", "org_repo_scanner.py"] 