all: format pylint mypy

.PHONY: format
format:
	poetry run isort .
	poetry run autopep8 -r --in-place .

.PHONY: pylint
pylint:
	poetry run pylint *.py

.PHONY: mypy
mypy:
	poetry run mypy *.py

