FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install essential Linux system dependencies for headless browser support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies and pre-fetch stealth browser binaries (non-fatal if upstream release is unavailable)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && (python -m camoufox fetch || echo "Camoufox binary fetch skipped; running with curl_cffi")

# Copy application source code
COPY . .

# Run the bot
CMD ["python", "bot.py"]

