#!/bin/sh
set -eu
if [ ! -d .git ]; then
    git init -b container-checks
    git add .
fi
uv run --locked prek install
uv run --locked prek run --all-files
