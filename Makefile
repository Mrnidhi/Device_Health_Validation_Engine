.PHONY: setup clean test lint format validate deploy help

setup:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	pip install dbt-snowflake dbt-utils
	cd dbt-semantic-layer && dbt deps

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	cd dbt-semantic-layer && dbt clean

lint:
	@echo "Running linters..."
	pylint spark-driver-behavior/jobs/*.py device-health-validation/validators/*.py claude-api-integration/*.py
	sqlfluff lint dbt-semantic-layer/models/

format:
	@echo "Formatting code..."
	black spark-driver-behavior/ device-health-validation/ claude-api-integration/
	sqlfluff format dbt-semantic-layer/models/

validate:
	@echo "Validating dbt models..."
	cd dbt-semantic-layer && dbt parse
	cd dbt-semantic-layer && dbt test

test:
	@echo "Running tests..."
	pytest tests/ -v --cov

deploy-dev:
	@echo "Deploying to development..."
	cd dbt-semantic-layer && dbt run --target dev
	cd ../spark-driver-behavior && python jobs/aggregate_trips.py --env dev
	cd ../device-health-validation && airflow dags test health_check_dag

deploy-prod:
	@echo "Deploying to production..."
	cd dbt-semantic-layer && dbt run --target prod --profiles-dir .
	cd ../spark-driver-behavior && python jobs/aggregate_trips.py --env prod
	cd ../device-health-validation && airflow dags unpause health_check_dag

help:
	@echo "Available targets:"
	@echo "  make setup      - Install all dependencies"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
	@echo "  make validate   - Validate dbt models"
	@echo "  make deploy-dev - Deploy to development"
	@echo "  make deploy-prod - Deploy to production"
