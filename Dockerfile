FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 POETRY_VIRTUALENVS_CREATE=false PORT=3001
WORKDIR /app
RUN pip install --no-cache-dir poetry==2.2.1
COPY pyproject.toml README.md ./
RUN poetry install --only main --no-interaction --no-ansi
COPY src ./src
RUN useradd --create-home agentguard
USER agentguard
EXPOSE 3001
CMD ["python", "-m", "src.server"]
