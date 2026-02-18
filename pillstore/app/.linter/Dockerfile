FROM docker.io/python:3.12

ARG BASE_DIR=/opt/linters

ENV \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.8.4 python3 -
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR ${BASE_DIR}
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --no-ansi
