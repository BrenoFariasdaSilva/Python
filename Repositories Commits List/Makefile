# Name of the virtual environment directory
VENV := venv

# Python command to use
PYTHON := python3

# Target names
.PHONY: all venv dependencies run

all: venv dependencies run

# Create the virtual environment if it doesn't exist
venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

# Install project dependencies
dependencies: venv
	$(VENV)/bin/pip install colorama pydriller

# Run the main Python script
run: venv
	clear; time $(VENV)/bin/python ./main.py
