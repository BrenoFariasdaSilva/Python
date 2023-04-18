#!/bin/sh

# Run:
# chmod +x dagster-installation.sh
# sudo ./dagster-installation.sh

project_name=tutorial-project # Environment variable

pip install dagster dagit

# Create var with the name of the project to be created

# Create a new project
dagster project scaffold --name $project_name

# Open the project folder
cd project_name

# Run the project in dev mode
dagster dev