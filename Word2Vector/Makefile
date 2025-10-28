# Name of the virtual environment directory
VENV := venv
OS := $(shell uname 2>/dev/null || echo Windows)

# Detect correct Python and Pip commands based on OS
ifeq ($(OS), Windows)
	PYTHON := python
	PIP := $(VENV)/Scripts/pip.exe
	PYTHON_CMD := $(VENV)/Scripts/python.exe
	CLEAR_CMD := cls
else
	PYTHON := python3
	PIP := $(VENV)/bin/pip
	PYTHON_CMD := $(VENV)/bin/python
	CLEAR_CMD := clear
endif

.PHONY: all venv dependencies run

all: venv dependencies run

venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	touch $(VENV)/bin/activate

run:
	$(CLEAR_CMD)
	$(PYTHON_CMD) ./word2vec.py

dependencies:
	$(PIP) install -r requirements.txt
