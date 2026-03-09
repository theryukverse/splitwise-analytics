FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if any (none needed for now)
# RUN apt-get update && apt-get install -y ...

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variable to indicate we are in Docker
ENV DOCKER=true

# Expose the default MCP port (SSE)
EXPOSE 5001

# Command to run the SSE server
CMD ["python", "mcp_server.py", "sse"]
