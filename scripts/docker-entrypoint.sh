#!/bin/sh
set -eu

python -m ouro_eval_lab.cli bootstrap \
  --root /lab/data/fixtures \
  --db /lab/data/lab.db \
  --seed "${OURO_LAB_SEED:-20260825}"

exec python -m ouro_eval_lab.cli serve \
  --db /lab/data/lab.db \
  --host 0.0.0.0 \
  --port 8080
