#!/usr/bin/env bash
# Render build step: install deps, collect static assets, run migrations.
set -o errexit

pip install --upgrade pip
pip install -r requirements/base.txt

# Needed when OpenAI quota/key fails and the adaptive provider falls back to spaCy.
python -m spacy download en_core_web_sm

python manage.py collectstatic --no-input
python manage.py migrate --no-input
