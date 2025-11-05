all: install format pylint mypy

.PHONY: install
install:
	poetry install

.PHONY: format
format:
	poetry run isort .
	poetry run autopep8 -r --in-place .

.PHONY: pylint
pylint:
	poetry run pylint yt_updater

.PHONY: mypy
mypy:
	poetry run mypy -p yt_updater --ignore-missing-imports


