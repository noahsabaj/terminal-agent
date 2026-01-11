# Terminal Coder - Sandboxed Container
# Uses Python 3.12 slim for smaller image size

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent
COPY agent.py .

# The workspace will be mounted from host for file access
# Mount point: /workspace/project

# Run the agent
ENTRYPOINT ["python", "agent.py"]
