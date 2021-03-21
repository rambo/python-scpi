# syntax=docker/dockerfile:1.1.7-experimental
#############################################
# Tox testsuite for multiple python version #
#############################################
FROM advian/tox-base:alpine as tox
ARG PYTHON_VERSIONS="3.8.7 3.9.1 3.7.9 3.6.12"
ARG POETRY_VERSION="1.1.4"
RUN for pyver in $PYTHON_VERSIONS; do pyenv install -s $pyver; done \
    && pyenv global $PYTHON_VERSIONS \
    && poetry self update $POETRY_VERSION || pip install -U poetry==$POETRY_VERSION \
    && python -m pip install -U tox \
    && apk add --no-cache \
        git \
    && poetry install \
    && docker/pre_commit_init.sh \
    && true

######################
# Base builder image #
######################
FROM python:3.7-alpine as builder_base

ENV \
  # locale
  LC_ALL=C.UTF-8 \
  # python:
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  # pip:
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # poetry:
  POETRY_VERSION=1.1.4


RUN apk add --no-cache \
        curl \
        git \
        bash \
        build-base \
        libffi-dev \
        linux-headers \
        openssl \
        openssl-dev \
        zeromq \
        tini \
        openssh-client \
        cargo \
    # githublab ssh
    && mkdir -p -m 0700 ~/.ssh && ssh-keyscan gitlab.com github.com | sort > ~/.ssh/known_hosts \
    # Install poetry package manager their way (pypi package sometimes has issues)
    && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 \
    && echo 'source $HOME/.poetry/env' >>/root/.profile \
    && source $HOME/.poetry/env \
    # We're in a container, do not create useless virtualenvs
    && poetry config virtualenvs.create false \
    && true

SHELL ["/bin/bash", "-lc"]


# Copy only requirements, to cache them in docker layer:
WORKDIR /pysetup
COPY ./poetry.lock ./pyproject.toml /pysetup/
# Install basic requirements (utilizing an internal docker wheelhouse if available)
RUN --mount=type=ssh pip3 install wheel \
    && poetry export -f requirements.txt --without-hashes -o /tmp/requirements.txt \
    && pip3 wheel --wheel-dir=/tmp/wheelhouse --trusted-host 172.17.0.1 --find-links=http://172.17.0.1:3141 -r /tmp/requirements.txt \
    && pip3 install --trusted-host 172.17.0.1 --find-links=http://172.17.0.1:3141 --find-links=/tmp/wheelhouse/ /tmp/wheelhouse/*.whl \
    && true


####################################
# Base stage for production builds #
####################################
FROM builder_base as production_build
# Copy entrypoint script
COPY ./docker/entrypoint.sh /docker-entrypoint.sh
# Only files needed by production setup
COPY ./poetry.lock ./pyproject.toml ./README.rst ./src /app/
WORKDIR /app
# Build the wheel package with poetry and add it to the wheelhouse
RUN --mount=type=ssh poetry build -f wheel --no-interaction --no-ansi \
    && cp dist/*.whl /tmp/wheelhouse \
    && chmod a+x /docker-entrypoint.sh \
    && true


#########################
# Main production build #
#########################
FROM python:3.7-alpine as production
COPY --from=production_build /tmp/wheelhouse /tmp/wheelhouse
COPY --from=production_build /docker-entrypoint.sh /docker-entrypoint.sh
WORKDIR /app
# Install system level deps for running the package (not devel versions for building wheels)
# and install the wheels we built in the previous step. generate default config
RUN --mount=type=ssh apk add --no-cache \
        bash \
        tini \
    && chmod a+x /docker-entrypoint.sh \
    && pip3 install --trusted-host 172.17.0.1 --find-links=http://172.17.0.1:3141 --find-links=/tmp/wheelhouse/ /tmp/wheelhouse/scpi-*.whl \
    && rm -rf /tmp/wheelhouse/ \
    # Do whatever else you need to
    && true
ENTRYPOINT ["/sbin/tini", "--", "/docker-entrypoint.sh"]


#####################################
# Base stage for development builds #
#####################################
FROM builder_base as devel_build
# Install deps
WORKDIR /pysetup
RUN --mount=type=ssh poetry install --no-interaction --no-ansi \
    && true


#0############
# Run tests #
#############
FROM devel_build as test
COPY . /app
WORKDIR /app
ENTRYPOINT ["/sbin/tini", "--", "docker/entrypoint-test.sh"]
# Re run install to get the service itself installed
RUN --mount=type=ssh poetry install --no-interaction --no-ansi \
    && docker/pre_commit_init.sh \
    && true


###########
# Hacking #
###########
FROM devel_build as devel_shell
# Copy everything to the image
COPY . /app
WORKDIR /app
RUN apk add --no-cache zsh \
    && sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" \
    && echo "source /root/.profile" >>/root/.zshrc \
    && pip3 install git-up \
    && true
ENTRYPOINT ["/bin/zsh", "-l"]
