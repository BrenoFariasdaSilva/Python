# Name of the virtual environment directory
VENV := venv
# Python command to use
PYTHON := python3

.PHONY: all venv dependencies run filter

all: venv dependencies run

venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	touch $(VENV)/bin/activate

run:
	clear; time $(VENV)/bin/python ./accountGames.py

filter:
	clear; time $(VENV)/bin/python ./gamesPlaytimeFilter.py

dependencies:
	$(VENV)/bin/pip install csvkit colorama requests
