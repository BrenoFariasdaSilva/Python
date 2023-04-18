#!/bin/sh

# Run:
# chmod +x dagster-installation.sh
# sudo ./dagster-installation.sh

pip install dagster dagit requests pandas matplotlib wordcloud dagster_duckdb dagster_duckdb_pandas

# Run the project in dev mode
dagster dev