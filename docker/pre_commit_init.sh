#!/bin/bash -l
if [ ! -d .git ]
then
  git init
  git checkout -b precommit_init
  git add .
fi
set -e
poetry run pre-commit install
poetry run pre-commit run --all-files
