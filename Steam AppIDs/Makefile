# Name of the virtual environment directory
VENV := venv
OS := $(shell uname 2>/dev/null || echo Windows)

# Detect correct Python and Pip commands based on OS
ifeq ($(OS), Windows)
	PYTHON := python
	PIP := $(VENV)/Scripts/pip.exe
	PYTHON_CMD := $(VENV)/Scripts/python.exe
	CLEAR_CMD := cls
	TIME_CMD :=
else
	PYTHON := python3
	PIP := $(VENV)/bin/pip
	PYTHON_CMD := $(VENV)/bin/python
	CLEAR_CMD := clear
	TIME_CMD := time
endif

.PHONY: all venv dependencies run filter

all: venv dependencies run filter

venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	touch $(VENV)/bin/activate

run:
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON_CMD) ./accountGames.py

filter:
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON_CMD) ./gamesPlaytimeFilter.py

dependencies:
	$(PIP) install -r requirements.txt
