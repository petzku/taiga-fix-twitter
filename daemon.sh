#!/bin/bash

cd -- $(dirname "$0")
echo "in: $PWD"
source venv/bin/activate
python main.py
