FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first (cache-friendly)
COPY pyproject.toml ./
RUN pip install --no-cache-dir requests>=2.32

# Copy source
COPY src/ ./src/

# Create the data directory (mounted at runtime, but provide a default)
RUN mkdir -p /data

# Run as non-root user for safety
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app /data
USER appuser

CMD ["python", "-m", "src.main"]
