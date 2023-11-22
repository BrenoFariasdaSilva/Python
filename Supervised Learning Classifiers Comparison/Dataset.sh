#!/bin/bash

# Run:
# chmod +x ./Dataset.sh
# ./Dataset.sh

# Extract "dataset.7z" if it exists
if [ -f "dataset.7z" ]; then
  7z x "dataset.7z"
  echo "Extracted 'dataset.7z'."
  rm "dataset.7z"
else
  echo "'dataset.7z' not found. Please download it"
fi

echo "Script execution completed."
