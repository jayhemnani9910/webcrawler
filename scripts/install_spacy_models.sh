#!/usr/bin/env bash
# Install common spaCy models for the knowledge extraction pipeline.
set -euo pipefail

MODEL=${1:-en_core_web_sm}

echo "Installing spaCy model: $MODEL"
python -m spacy download "$MODEL"
echo "Model $MODEL installed."
