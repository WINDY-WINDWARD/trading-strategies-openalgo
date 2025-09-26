# Makefile for Grid Trading Backtester

.PHONY: help dev test lint format web docker-build docker-run clean

# Default target
help:
	@echo "Available targets:"
	@echo "  dev          - Install development dependencies"
	@echo "  test         - Run test suite"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black"
	@echo "  web          - Start web dashboard"
	@echo "  backtest     - Run CLI backtest with default config"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  clean        - Clean cache and temporary files"

# Development setup
dev:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pre-commit pytest-cov
	pre-commit install

# Testing
test:
	python -m pytest tests/ -v --cov=app

# Code quality
lint:
	ruff check app/ scripts/ tests/
	black --check app/ scripts/ tests/

format:
	black app/ scripts/ tests/
	ruff --fix app/ scripts/ tests/

# Run web dashboard
web:
	python scripts/launch_web.py

# Run CLI backtest
backtest:
	python -m scripts.backtest --config config.yaml --verbose

# Docker
docker-build:
	docker build -t grid-backtest .

docker-run:
	docker run -p 8000:8000 -e OPENALGO_API_KEY=${OPENALGO_API_KEY} grid-backtest

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
