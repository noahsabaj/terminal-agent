# Terminal Agent - Sandboxed Container
# Transparent to user - they won't know they're in a container

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the agent code
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent
COPY agent.py .

# Create workspace directory (will be mounted from host)
RUN mkdir -p /workspace/project

# Set the workspace as the default directory
WORKDIR /workspace/project

# Run the agent - it will operate on files in /workspace/project
ENTRYPOINT ["python", "/app/agent.py"]
