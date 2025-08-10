import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.database import SessionLocal
from app.models.feedback import Feedback, FeedbackLabel
from app.models.cluster import Cluster
from app.models.label import Label
from app.nlp.classifier import FeedbackClassifier
from app.nlp.embedder import TextEmbedder
from sklearn.cluster import HDBSCAN
import numpy as np
import os

logger = logging.getLogger(__name__)

class NLUWorker:
    def __init__(self):
        """Initialize the NLU worker."""
        self.db = SessionLocal()
        self.classifier = FeedbackClassifier()
        self.embedder = TextEmbedder()
        
        # Initialize labels if they don't exist
        self._ensure_labels()
    
    def _ensure_labels(self):
        """Ensure all default labels exist in the database."""
        try:
            existing_labels = {label.name for label in self.db.query(Label).all()}
            
            for label_name in self.classifier.default_labels:
                if label_name not in existing_labels:
                    label_type = label_name.split('/')[0] if '/' in label_name else 'general'
                    label = Label(name=label_name, type=label_type)
                    self.db.add(label)
            
            self.db.commit()
            logger.info("Ensured all default labels exist")
        except Exception as e:
            logger.error(f"Failed to ensure labels: {e}")
            self.db.rollback()
    
    def process_feedback(self, feedback_id: int) -> bool:
        """Process a single feedback item for NLU."""
        try:
            feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not feedback:
                logger.error(f"Feedback {feedback_id} not found")
                return False
            
            if not feedback.text_clean:
                logger.warning(f"Feedback {feedback_id} has no clean text")
                return False
            
            # Step 1: Classify feedback
            classification = self.classifier.classify(feedback.text_clean)
            
            # Step 2: Store labels
            self._store_labels(feedback.id, classification)
            
            # Step 3: Generate embedding
            embedding = self.embedder.embed_text(feedback.text_clean)
            
            # Step 4: Assign to cluster or create new one
            cluster_id = self._assign_to_cluster(feedback.text_clean, embedding)
            if cluster_id:
                feedback.cluster_id = cluster_id
                self.db.commit()
            
            logger.info(f"Processed NLU for feedback {feedback_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process NLU for feedback {feedback_id}: {e}")
            self.db.rollback()
            return False
    
    def _store_labels(self, feedback_id: int, classification: Dict[str, Any]):
        """Store classification labels for feedback."""
        try:
            # Get label objects
            label_objects = {}
            for label_name in classification['labels']:
                label = self.db.query(Label).filter(Label.name == label_name).first()
                if label:
                    label_objects[label_name] = label
            
            # Store feedback-label relationships
            for label_name, score in zip(classification['labels'], classification['scores']):
                if label_name in label_objects:
                    feedback_label = FeedbackLabel(
                        feedback_id=feedback_id,
                        label_id=label_objects[label_name].id,
                        score=score
                    )
                    self.db.add(feedback_label)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to store labels: {e}")
            raise
    
    def _assign_to_cluster(self, text: str, embedding: np.ndarray) -> int:
        """Assign feedback to existing cluster or create new one."""
        try:
            # Get existing clusters
            existing_clusters = self.db.query(Cluster).all()
            
            if not existing_clusters:
                # Create first cluster
                cluster = self._create_cluster(embedding, text)
                return cluster.id
            
            # Find best matching cluster
            best_cluster = None
            best_similarity = 0
            similarity_threshold = 0.7  # Configurable
            
            for cluster in existing_clusters:
                if cluster.centroid_embedding:
                    cluster_embedding = self.embedder.bytes_to_embedding(cluster.centroid_embedding)
                    similarity = self.embedder.similarity(text, cluster_embedding)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_cluster = cluster
            
            if best_similarity > similarity_threshold and best_cluster:
                # Update existing cluster
                self._update_cluster(best_cluster, embedding)
                return best_cluster.id
            else:
                # Create new cluster
                cluster = self._create_cluster(embedding, text)
                return cluster.id
                
        except Exception as e:
            logger.error(f"Failed to assign to cluster: {e}")
            raise
    
    def _create_cluster(self, embedding: np.ndarray, text: str) -> Cluster:
        """Create a new cluster."""
        cluster = Cluster(
            centroid_embedding=self.embedder.embedding_to_bytes(embedding),
            summary=text[:200],  # Simple summary for now
            size=1,
            confidence=1.0
        )
        self.db.add(cluster)
        self.db.commit()
        return cluster
    
    def _update_cluster(self, cluster: Cluster, new_embedding: np.ndarray):
        """Update existing cluster with new embedding."""
        if cluster.centroid_embedding:
            old_embedding = self.embedder.bytes_to_embedding(cluster.centroid_embedding)
            # Simple average update
            new_centroid = (old_embedding + new_embedding) / 2
            cluster.centroid_embedding = self.embedder.embedding_to_bytes(new_centroid)
            cluster.size += 1
            self.db.commit()
    
    def run(self):
        """Main worker loop."""
        logger.info("Starting NLU worker...")
        
        while True:
            try:
                # Process unprocessed feedback
                unprocessed = self.db.query(Feedback).filter(
                    Feedback.status == 'new',
                    Feedback.text_clean.isnot(None)
                ).limit(10).all()
                
                for feedback in unprocessed:
                    self.process_feedback(feedback.id)
                
                # Sleep if no work
                if not unprocessed:
                    import time
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                logger.info("Stopping NLU worker...")
                break
            except Exception as e:
                logger.error(f"Error in NLU worker: {e}")
                continue
        
        self.db.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'db'):
            self.db.close() 