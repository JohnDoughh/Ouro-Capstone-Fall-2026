FROM python:3.12-slim

WORKDIR /lab
COPY . .
RUN python -m compileall -q ouro_eval_lab \
    && python -m ouro_eval_lab.cli seed --root data/fixtures --seed 20260825 \
    && python -m ouro_eval_lab.cli init-db --db data/lab.db \
    && python -m ouro_eval_lab.cli ingest --db data/lab.db --manifest data/fixtures/manifest.json

EXPOSE 8080
CMD ["python", "-m", "ouro_eval_lab.cli", "serve", "--db", "data/lab.db", "--host", "0.0.0.0", "--port", "8080"]
