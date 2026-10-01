#!/bin/sh
set -eu
if [ "$#" -gt 0 ]; then
    exec "$@"
fi
uv run --locked docker/prek_init.sh
uv run --locked pytest --junitxml=pytest.xml tests/
uv run --locked pyrefly check
uv run --locked bandit -r src --skip B101
