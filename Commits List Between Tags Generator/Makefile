# Name of the virtual environment directory
VENV := venv
# Python command to use
PYTHON := python3

# Target names
.PHONY: all venv dependencies run

all: venv dependencies run

venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

dependencies: venv
	$(VENV)/bin/pip install colorama pydriller

run: venv
	clear; time $(VENV)/bin/python ./main.py
