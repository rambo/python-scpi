#!/bin/bash -l
set -e
if [ "$#" -eq 0 ]; then
  # TODO: Put your actual program start here
  exec true
else
  exec "$@"
fi
