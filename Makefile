.PHONY: help install install-dev run run-api run-bot test test-cov lint format clean docker-build docker-up docker-down migrate migrate-create migrate-upgrade migrate-downgrade

help: ## Show this help message
	@echo "ProductSync - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv pip install .

install-dev: ## Install development dependencies
	uv pip install .[dev]

run: ## Run the full application (API + Discord bot)
	python main.py

run-api: ## Run only the Flask API
	FLASK_ENV=development python -c "from app.api.app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5000, debug=True)"

run-bot: ## Run only the Discord bot
	python -c "from app.discord_bot import run_discord_bot; run_discord_bot()"

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term

lint: ## Run linting
	flake8 app/ tests/
	mypy app/

format: ## Format code with black
	black app/ tests/

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/

docker-build: ## Build Docker image
	docker build -t productsync .

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-down: ## Stop all services with Docker Compose
	docker-compose down

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create name=migration_name)
	alembic revision --autogenerate -m "$(name)"

migrate-upgrade: ## Upgrade to latest migration
	alembic upgrade head

migrate-downgrade: ## Downgrade one migration
	alembic downgrade -1

setup-db: ## Set up the database and run initial migration
	@echo "Setting up database..."
	@echo "Make sure PostgreSQL is running and accessible"
	@echo "Update your .env file with correct DATABASE_URL"
	@echo "Then run: make migrate"

dev-setup: ## Set up development environment
	@echo "Setting up development environment..."
	@echo "1. Copy env.example to .env and fill in your values"
	@echo "2. Install dependencies: make install-dev"
	@echo "3. Set up database: make setup-db"
	@echo "4. Start services: make docker-up"
	@echo "5. Run the application: make run" 