# Streamlit UI for ColdEmails.
#
# Note: the default `claude_cli` draft mode needs the Claude Code CLI and a
# login, which containers don't have — set ANTHROPIC_API_KEY and use the
# "Claude API key" draft mode (or "template") when running in Docker.
#
#   docker build -t coldemails .
#   docker run --rm -p 8501:8501 --env-file .env -v $(pwd)/data:/data coldemails

FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY coldemails/ coldemails/
COPY app.py pyproject.toml ./

ENV COLDEMAILS_DB=/data/coldemails.db
VOLUME /data

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
