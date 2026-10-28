FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
COPY pyproject.toml README.md ./
COPY iqgram ./iqgram
COPY miko.py ./
RUN python -m pip install --no-cache-dir --upgrade pip && python -m pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 iqgram && mkdir -p /app/data && chown 10001:10001 /app/data
USER 10001
VOLUME ["/app/data"]
CMD ["python", "miko.py", "bot"]
