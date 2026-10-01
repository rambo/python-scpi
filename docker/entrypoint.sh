#!/bin/sh
set -eu
if [ "$#" -eq 0 ]; then
    exec python -c 'import scpi; print(scpi.__version__)'
fi
exec "$@"
