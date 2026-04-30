# Build stage - compile C extensions with build-essential
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY src/requirements.txt ./

RUN pip install --upgrade pip && \
    pip install 'MarkupSafe==2.0.1' && \
    pip install -r requirements.txt

# Production stage - no build tools needed
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY src/copilot_agent ./copilot_agent

# Default command: run the agent
CMD ["python", "-m", "copilot_agent"]
