FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Copy project files
COPY src/requirements.txt ./
COPY src/copilot_agent ./copilot_agent

# Create and activate virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install 'MarkupSafe==2.0.1' && \
    pip install -r requirements.txt

# Default command: run the agent
CMD ["python", "-m", "copilot_agent"]
