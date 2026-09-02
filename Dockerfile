FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY detective ./detective

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# `docker compose up` → the web UI. Any CLI command works too:
#   docker compose run --rm detective investigate <repo>
ENTRYPOINT ["python", "-m", "detective"]
CMD ["serve"]
