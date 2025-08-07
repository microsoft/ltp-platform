FROM python:3.9-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/pyproject.toml ./
COPY src/copilot_agent ./copilot_agent

ENV RYE_HOME="/opt/rye"
ENV PATH="$RYE_HOME/shims:$PATH"
ENV RYE_NO_AUTO_INSTALL=1
ENV RYE_INSTALL_OPTION="--yes"
RUN curl -sSf https://rye.astral.sh/get | bash

RUN pip install 'MarkupSafe==2.0.1'

# Use Rye to install dependencies
RUN rye sync

# Default command: run the agent as in development
CMD ["rye", "run", "copilot-agent"]
