#!/bin/bash
PYLINTRC=`dirname $0`/.pylintrc
FLAKE8RC=`dirname $0`/.flake8
find . -name '._*' | xargs rm
for f in $(find . -name '*.py' -and -not -path '*/venv/*' -and -not -path '*/build/*')
do
    echo "================="
    echo $f
    autopep8 -ri --max-line-length=10000 $f
    flake8 --config=$FLAKE8RC $f
    isort -rc $f
    pylint --rcfile=$PYLINTRC $f
done

