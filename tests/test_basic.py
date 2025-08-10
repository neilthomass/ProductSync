"""
Basic tests for ProductSync application
"""

import pytest
from app.api.app import create_app
from app.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app('testing')
    return app


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'
    assert response.json['service'] == 'ProductSync API'


def test_404_error(client):
    """Test 404 error handling."""
    response = client.get('/nonexistent')
    assert response.status_code == 404
    assert 'error' in response.json


def test_app_creation():
    """Test that the Flask app can be created."""
    app = create_app('testing')
    assert app is not None
    assert app.config['TESTING'] is True


def test_database_models_importable():
    """Test that all database models can be imported."""
    try:
        from app.models.feedback import Feedback
        from app.models.label import Label
        from app.models.cluster import Cluster
        from app.models.initiative import Initiative
        from app.models.product_area import ProductArea
        from app.models.source_user import SourceUser
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import database models: {e}")


def test_nlp_components_importable():
    """Test that all NLP components can be imported."""
    try:
        from app.nlp.preprocessor import TextPreprocessor
        from app.nlp.classifier import TextClassifier
        from app.nlp.embedder import TextEmbedder
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import NLP components: {e}")


def test_workers_importable():
    """Test that all worker components can be imported."""
    try:
        from app.workers.ingest_worker import IngestWorker
        from app.workers.nlu_worker import NLUWorker
        from app.workers.priority_worker import PriorityWorker
        from app.workers.actions_worker import ActionsWorker
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import worker components: {e}") 