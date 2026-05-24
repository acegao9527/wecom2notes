# Multi-stage build for wecom2notes - WeCom to Notes Connector
FROM python:3.12-slim

# Set timezone
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

# Copy source code (includes SQL files)
COPY src /app/src

# Copy project root files
COPY main.py .
COPY config /app/config

# Copy SDK libraries (both x86_64 and ARM64)
COPY lib /app/lib

# Runtime health checks use Python stdlib, so no extra OS packages are required.

# Copy correct SDK to /usr/local/lib based on platform architecture
RUN if [ -f "lib/wework-arm64/libWeWorkFinanceSdk_C.so" ]; then \
        cp lib/wework-arm64/libWeWorkFinanceSdk_C.so /usr/local/lib/libWeWorkFinanceSdk.so && ldconfig; \
    elif [ -f "lib/wework-x86_64/libWeWorkFinanceSdk_C.so" ]; then \
        cp lib/wework-x86_64/libWeWorkFinanceSdk_C.so /usr/local/lib/libWeWorkFinanceSdk.so && ldconfig; \
    fi

# Set environment variables
ENV PYTHONPATH=/app:${PYTHONPATH}
ENV LD_LIBRARY_PATH=/usr/local/lib:/app/lib:${LD_LIBRARY_PATH}
ENV APP_PORT=${APP_PORT:-8001}

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE ${APP_PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD sh -c "python -c \"import os, urllib.request; urllib.request.urlopen('http://localhost:%s/' % os.getenv('APP_PORT', '8001'))\"" || exit 1

# Start the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${APP_PORT}"]
