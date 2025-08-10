import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.database import SessionLocal
from app.models.feedback import Feedback, FeedbackLabel
from app.models.cluster import Cluster
from app.models.label import Label
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

class PriorityWorker:
    def __init__(self):
        """Initialize the priority worker."""
        self.db = SessionLocal()
        
        # Priority weights as specified in README
        self.weights = {
            'severity': 0.3,
            'reach': 0.25,
            'novelty': 0.2,
            'momentum': 0.15,
            'confidence': 0.1
        }
    
    def calculate_priority_score(self, feedback_id: int) -> float:
        """Calculate priority score for feedback as specified in README."""
        try:
            feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not feedback:
                return 0.0
            
            # Calculate individual components
            severity = self._calculate_severity(feedback)
            reach = self._calculate_reach(feedback)
            novelty = self._calculate_novelty(feedback)
            momentum = self._calculate_momentum(feedback)
            confidence = self._calculate_confidence(feedback)
            
            # Weighted combination
            priority_score = (
                self.weights['severity'] * severity +
                self.weights['reach'] * reach +
                self.weights['novelty'] * novelty +
                self.weights['momentum'] * momentum +
                self.weights['confidence'] * confidence
            )
            
            # Update feedback with priority score
            feedback.priority_score = priority_score
            self.db.commit()
            
            logger.info(f"Calculated priority score {priority_score:.3f} for feedback {feedback_id}")
            return priority_score
            
        except Exception as e:
            logger.error(f"Failed to calculate priority for feedback {feedback_id}: {e}")
            self.db.rollback()
            return 0.0
    
    def _calculate_severity(self, feedback: Feedback) -> float:
        """Calculate severity score (0-1) based on bug/impact language and rules."""
        try:
            # Get labels for this feedback
            labels = self.db.query(Label).join(FeedbackLabel).filter(
                FeedbackLabel.feedback_id == feedback.id
            ).all()
            
            severity_score = 0.0
            
            # Rule-based severity scoring
            for label in labels:
                if 'bug/crash' in label.name:
                    severity_score = max(severity_score, 0.9)
                elif 'bug/performance' in label.name:
                    severity_score = max(severity_score, 0.7)
                elif 'security' in label.name:
                    severity_score = max(severity_score, 0.95)
                elif 'bug' in label.name:
                    severity_score = max(severity_score, 0.6)
                elif 'ux/usability' in label.name:
                    severity_score = max(severity_score, 0.4)
                elif 'feature' in label.name:
                    severity_score = max(severity_score, 0.3)
                elif 'docs' in label.name:
                    severity_score = max(severity_score, 0.2)
            
            # Text-based severity indicators
            text_lower = feedback.text_clean.lower()
            severity_indicators = {
                'crash': 0.9, 'broken': 0.8, 'error': 0.7, 'fail': 0.7,
                'slow': 0.6, 'lag': 0.6, 'freeze': 0.8, 'bug': 0.6,
                'urgent': 0.8, 'critical': 0.9, 'blocking': 0.8
            }
            
            for indicator, score in severity_indicators.items():
                if indicator in text_lower:
                    severity_score = max(severity_score, score)
            
            return min(severity_score, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate severity: {e}")
            return 0.5
    
    def _calculate_reach(self, feedback: Feedback) -> float:
        """Calculate reach score based on user weight, dedup count, channel importance."""
        try:
            # Channel importance (Slack internal < Discord external as specified in README)
            channel_weights = {
                'slack': 0.6,  # Internal
                'discord': 1.0,  # External
                'notion': 0.8   # Mixed
            }
            
            channel_weight = channel_weights.get(feedback.source, 0.5)
            
            # Deduplication count (how many similar feedback items)
            if feedback.cluster_id:
                cluster_size = self.db.query(Cluster).filter(
                    Cluster.id == feedback.cluster_id
                ).first().size
                dedup_multiplier = min(cluster_size / 10.0, 2.0)  # Cap at 2x
            else:
                dedup_multiplier = 1.0
            
            # User weight (internal vs external)
            user_weight = 0.8  # Default, could be enhanced with user analysis
            
            reach_score = channel_weight * dedup_multiplier * user_weight
            return min(reach_score, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate reach: {e}")
            return 0.5
    
    def _calculate_novelty(self, feedback: Feedback) -> float:
        """Calculate novelty score (inverse cosine sim to resolved clusters)."""
        try:
            if not feedback.cluster_id:
                return 1.0  # New cluster = high novelty
            
            # Get resolved feedback in the same cluster
            resolved_count = self.db.query(Feedback).filter(
                and_(
                    Feedback.cluster_id == feedback.cluster_id,
                    Feedback.status == 'resolved'
                )
            ).count()
            
            # Higher novelty if fewer resolved items
            novelty_score = 1.0 / (1.0 + resolved_count)
            return novelty_score
            
        except Exception as e:
            logger.error(f"Failed to calculate novelty: {e}")
            return 0.5
    
    def _calculate_momentum(self, feedback: Feedback) -> float:
        """Calculate momentum score based on recent mentions and growth."""
        try:
            # Recent mentions in the same cluster
            if feedback.cluster_id:
                # Count feedback in last 7 days vs previous 7 days
                now = datetime.utcnow()
                week_ago = now - timedelta(days=7)
                two_weeks_ago = now - timedelta(days=14)
                
                recent_count = self.db.query(Feedback).filter(
                    and_(
                        Feedback.cluster_id == feedback.cluster_id,
                        Feedback.created_at >= week_ago
                    )
                ).count()
                
                previous_count = self.db.query(Feedback).filter(
                    and_(
                        Feedback.cluster_id == feedback.cluster_id,
                        Feedback.created_at >= two_weeks_ago,
                        Feedback.created_at < week_ago
                    )
                ).count()
                
                if previous_count == 0:
                    momentum_score = 1.0 if recent_count > 0 else 0.0
                else:
                    growth_rate = (recent_count - previous_count) / previous_count
                    momentum_score = min(max(growth_rate, -0.5), 1.0)  # Clamp to [-0.5, 1.0]
                    momentum_score = (momentum_score + 0.5) / 1.5  # Normalize to [0, 1]
            else:
                momentum_score = 1.0  # New cluster
            
            return momentum_score
            
        except Exception as e:
            logger.error(f"Failed to calculate momentum: {e}")
            return 0.5
    
    def _calculate_confidence(self, feedback: Feedback) -> float:
        """Calculate confidence score based on model certainty, text length, agreement."""
        try:
            # Model certainty (average label score)
            label_scores = self.db.query(FeedbackLabel.score).filter(
                FeedbackLabel.feedback_id == feedback.id
            ).all()
            
            if label_scores:
                avg_score = np.mean([score for (score,) in label_scores])
                model_confidence = avg_score
            else:
                model_confidence = 0.5
            
            # Text length confidence (longer text = more confident)
            text_length = len(feedback.text_clean) if feedback.text_clean else 0
            length_confidence = min(text_length / 100.0, 1.0)  # Normalize to [0, 1]
            
            # Agreement among models (if multiple labels, higher agreement = higher confidence)
            if len(label_scores) > 1:
                agreement_confidence = 1.0 - np.std([score for (score,) in label_scores])
            else:
                agreement_confidence = 0.5
            
            # Combine confidence factors
            confidence_score = (
                0.5 * model_confidence +
                0.3 * length_confidence +
                0.2 * agreement_confidence
            )
            
            return confidence_score
            
        except Exception as e:
            logger.error(f"Failed to calculate confidence: {e}")
            return 0.5
    
    def run(self):
        """Main worker loop."""
        logger.info("Starting priority worker...")
        
        while True:
            try:
                # Process feedback without priority scores
                unprocessed = self.db.query(Feedback).filter(
                    Feedback.priority_score.is_(None),
                    Feedback.text_clean.isnot(None)
                ).limit(10).all()
                
                for feedback in unprocessed:
                    self.calculate_priority_score(feedback.id)
                
                # Sleep if no work
                if not unprocessed:
                    import time
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                logger.info("Stopping priority worker...")
                break
            except Exception as e:
                logger.error(f"Error in priority worker: {e}")
                continue
        
        self.db.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'db'):
            self.db.close() 