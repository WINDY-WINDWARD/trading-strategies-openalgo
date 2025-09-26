# Makefile for Grid Trading Backtester

.PHONY: help dev web clean

# Default target
help:
	@echo "Available targets:"
	@echo "  dev          - Install development dependencies"
	@echo "  web          - Start web dashboard"
	@echo "  live         - Start live trading bot"
	@echo "  clean        - Clean cache and temporary files"

# Development setup
dev:
	pip install --upgrade pip
	pip install -r requirements.txt
	
# Run web dashboard
web:
	python scripts/launch_web.py

live: 
	python .\launch_trading_bot.py

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
