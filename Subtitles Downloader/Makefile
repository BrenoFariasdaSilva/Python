# Variables
VENV := venv
OS := $(shell uname 2>/dev/null || echo Windows)
DEPS_STAMP := $(VENV)/.deps-installed

# Detect correct Python and Pip commands based on OS
ifeq ($(OS), Windows)
	PYTHON := $(VENV)/Scripts/python.exe
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python
	CLEAR_CMD := cls
	TIME_CMD :=
else
	PYTHON := $(VENV)/bin/python3
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python3
	CLEAR_CMD := clear
	TIME_CMD := time
endif

# Main target that runs the scripts
all: run

# Main Scripts:
run: $(DEPS_STAMP)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) ./main.py

# Setup Virtual Environment and Install Dependencies
$(PYTHON):
	$(PYTHON_CMD) -m venv $(VENV)

$(VENV)/pip-ready: $(PYTHON)
	$(PYTHON) -m ensurepip --upgrade
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -c "from pathlib import Path; Path(r'$(VENV)/pip-ready').touch()"

$(DEPS_STAMP): requirements.txt $(VENV)/pip-ready
	$(PIP) install -r requirements.txt
	$(PYTHON) -c "from pathlib import Path; Path(r'$(DEPS_STAMP)').touch()"

# Install the project dependencies
dependencies: $(DEPS_STAMP)

# Generate requirements.txt from the current venv
generate_requirements: $(DEPS_STAMP)
	$(PIP) freeze > requirements.txt

# Utility rule for cleaning the project
clean:
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete || del /S /Q *.pyc 2>nul
	find . -type d -name '__pycache__' -delete || rmdir /S /Q __pycache__ 2>nul

.PHONY: run clean dependencies generate_requirements
