#!/bin/sh

# Run:
# chmod +x install.sh
# sudo ./install.sh

# Python:
sudo apt-get install python3 python3-venv python3-pip -y
# sudo apt install python-is-python3

# Jupyter using Pip
pip install jupyterlab
pip install notebook
pip install ipykernel
# Launch: jupyter-lab or jupyter notebook in terminal