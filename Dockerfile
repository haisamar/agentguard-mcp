FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=3001
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY src ./src
RUN useradd --create-home agentguard
USER agentguard
EXPOSE 3001
CMD ["python", "-m", "src.server"]
