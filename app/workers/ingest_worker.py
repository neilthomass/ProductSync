import json
import logging
from typing import Dict, Any
from redis import Redis
from sqlalchemy.orm import Session
from app.models.database import get_db, SessionLocal
from app.models.feedback import Feedback
from app.nlp.preprocessor import TextPreprocessor
import os

logger = logging.getLogger(__name__)

class IngestWorker:
    def __init__(self, redis_url: str = None):
        """Initialize the ingest worker."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = Redis.from_url(self.redis_url)
        self.preprocessor = TextPreprocessor()
        self.db = SessionLocal()
    
    def process_feedback(self, payload: Dict[str, Any]) -> bool:
        """Process a single feedback payload."""
        try:
            # Check for duplicate using Redis
            key = f"dupe:{payload['source']}:{payload['source_msg_id']}"
            if not self.redis_client.setnx(key, 1):
                logger.info(f"Duplicate feedback detected: {key}")
                return False
            
            # Set expiration for deduplication key (7 days as specified in README)
            self.redis_client.expire(key, 7 * 24 * 3600)
            
            # Preprocess text
            text_raw = payload.get('text', '')
            text_clean = self.preprocessor.preprocess(text_raw)
            
            # Create feedback record
            feedback = Feedback(
                source=payload['source'],
                source_msg_id=payload['source_msg_id'],
                author_id=payload['author_id'],
                text_raw=text_raw,
                text_clean=text_clean,
                status='new'
            )
            
            # Add channel info if available
            if 'channel' in payload:
                # Could store channel info in a separate field or table
                pass
            
            # Save to database
            self.db.add(feedback)
            self.db.commit()
            
            logger.info(f"Processed feedback {feedback.id} from {payload['source']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process feedback: {e}")
            self.db.rollback()
            return False
    
    def run(self):
        """Main worker loop."""
        logger.info("Starting ingest worker...")
        
        while True:
            try:
                # Pop from Redis queue (blocking)
                result = self.redis_client.blpop("ingest:feedback", timeout=1)
                
                if result:
                    _, payload_json = result
                    payload = json.loads(payload_json)
                    self.process_feedback(payload)
                else:
                    # No message, continue
                    continue
                    
            except KeyboardInterrupt:
                logger.info("Stopping ingest worker...")
                break
            except Exception as e:
                logger.error(f"Error in ingest worker: {e}")
                continue
        
        self.db.close()
        self.redis_client.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'redis_client'):
            self.redis_client.close() 