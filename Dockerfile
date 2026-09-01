FROM python:3.12-slim

WORKDIR /lab
COPY . .
RUN python -m compileall -q ouro_eval_lab \
    && chmod +x /lab/scripts/docker-entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/lab/scripts/docker-entrypoint.sh"]
