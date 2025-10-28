# Variables
VENV := venv
OS := $(shell uname 2>/dev/null || echo Windows)

# Detect correct Python and Pip commands based on OS
ifeq ($(OS), Windows)
	PYTHON := $(VENV)/Scripts/python.exe
	PIP := $(VENV)/Scripts/pip.exe
	PYTHON_CMD := python
	CLEAR_CMD := cls
	TIME_CMD :=
	CHMOD_CMD :=
else
	PYTHON := $(VENV)/bin/python3
	PIP := $(VENV)/bin/pip
	PYTHON_CMD := python3
	CLEAR_CMD := clear
	TIME_CMD := time
	CHMOD_CMD := chmod +x
endif

# Main target that runs the scripts
all: run

# Main Scripts:
run: $(VENV)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) ./main.py

code_metrics_script: $(VENV)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) code_metrics.py

metrics_changes_script: $(VENV)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) metrics_changes.py

# Auxiliar Scripts:
empty_folders_script: $(VENV)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) Scripts/empty_folders.py

extract_zip_files_script: $(VENV)
	$(CHMOD_CMD) Scripts/extract_zip_files.sh
	$(CLEAR_CMD)
	$(TIME_CMD) ./Scripts/extract_zip_files.sh

generate_short_zip_files_script: $(VENV)
	$(CHMOD_CMD) Scripts/generate_short_zip_files.sh
	$(CLEAR_CMD)
	$(TIME_CMD) ./Scripts/generate_short_zip_files.sh

generate_zip_files_script: $(VENV)
	$(CHMOD_CMD) Scripts/generate_zip_files.sh
	$(CLEAR_CMD)
	$(TIME_CMD) ./Scripts/generate_zip_files.sh

move_extracted_files_script: $(VENV)
	$(CHMOD_CMD) Scripts/move_extracted_files.sh
	$(CLEAR_CMD)
	$(TIME_CMD) ./Scripts/move_extracted_files.sh

track_files_script: $(VENV)
	$(CLEAR_CMD)
	$(TIME_CMD) $(PYTHON) Scripts/track_files.py

# Setup Virtual Environment and Install Dependencies
$(VENV):
	$(PYTHON_CMD) -m venv $(VENV)
	$(PIP) install -r requirements.txt

# Install the project dependencies
dependencies: $(VENV)

# Generate requirements.txt from the current venv
generate_requirements: $(VENV)
	$(PIP) freeze > requirements.txt

# Utility rule for cleaning the project
clean:
	rm -rf $(VENV) || rmdir /S /Q $(VENV) 2>nul
	find . -type f -name '*.pyc' -delete || del /S /Q *.pyc 2>nul
	find . -type d -name '__pycache__' -delete || rmdir /S /Q __pycache__ 2>nul

.PHONY: all run clean code_metrics_script metrics_changes_script empty_folders_script extract_zip_files_script generate_short_zip_files_script generate_zip_files_script move_extracted_files_script track_files_script dependencies generate_requirements
