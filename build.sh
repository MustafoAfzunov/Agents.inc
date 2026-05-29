#!/usr/bin/env bash
# Render build step: install deps, collect static assets, run migrations.
set -o errexit

pip install --upgrade pip
pip install -r requirements/base.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input
