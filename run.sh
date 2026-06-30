#!/bin/bash
echo "Setting up Godrej Market Share Dashboard..."
pip install -r requirements.txt
echo "Starting dashboard..."
streamlit run app.py
