#!/usr/bin/env bash
# Install common spaCy models for the knowledge extraction pipeline.
set -euo pipefail

MODEL=${1:-en_core_web_sm}

# spaCy is not in requirements.txt, so the download step used to abort under
# set -e with "No module named spacy" before fetching anything.
if ! python -c "import spacy" 2>/dev/null; then
  echo "spaCy is not installed; installing it first."
  python -m pip install spacy
fi

echo "Installing spaCy model: $MODEL"
python -m spacy download "$MODEL"
echo "Model $MODEL installed."
