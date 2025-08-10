import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.database import SessionLocal
from app.models.feedback import Feedback
from app.models.cluster import Cluster
from app.models.initiative import Initiative
from app.models.label import Label
from datetime import datetime, timedelta
import os
import requests

logger = logging.getLogger(__name__)

class ActionsWorker:
    def __init__(self):
        """Initialize the actions worker."""
        self.db = SessionLocal()
        
        # Configuration
        self.jira_threshold = float(os.getenv("JIRA_THRESHOLD", "0.7"))
        self.jira_base_url = os.getenv("JIRA_BASE_URL")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        
        # Check if JIRA integration is configured
        self.jira_enabled = all([
            self.jira_base_url,
            self.jira_username,
            self.jira_api_token
        ])
        
        if not self.jira_enabled:
            logger.warning("JIRA integration not configured - skipping JIRA actions")
    
    def process_actions(self, feedback_id: int) -> bool:
        """Process actions for a feedback item."""
        try:
            feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not feedback:
                return False
            
            # Check if action is needed
            if self._should_create_jira(feedback):
                self._create_jira_issue(feedback)
            
            # Update feedback status
            feedback.status = 'triaged'
            self.db.commit()
            
            logger.info(f"Processed actions for feedback {feedback_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process actions for feedback {feedback_id}: {e}")
            self.db.rollback()
            return False
    
    def _should_create_jira(self, feedback: Feedback) -> bool:
        """Determine if JIRA issue should be created."""
        if not self.jira_enabled:
            return False
        
        # Check priority threshold
        if feedback.priority_score and feedback.priority_score > self.jira_threshold:
            return True
        
        # Check cluster momentum spike
        if feedback.cluster_id:
            if self._check_cluster_momentum_spike(feedback.cluster_id):
                return True
        
        return False
    
    def _check_cluster_momentum_spike(self, cluster_id: int) -> bool:
        """Check if cluster has momentum spike."""
        try:
            # Get recent feedback in cluster
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)
            
            recent_count = self.db.query(Feedback).filter(
                and_(
                    Feedback.cluster_id == cluster_id,
                    Feedback.created_at >= day_ago
                )
            ).count()
            
            weekly_avg = self.db.query(func.avg(func.count(Feedback.id))).filter(
                and_(
                    Feedback.cluster_id == cluster_id,
                    Feedback.created_at >= week_ago
                )
            ).scalar() or 0
            
            # Spike if recent count > 2x weekly average
            return recent_count > (weekly_avg * 2)
            
        except Exception as e:
            logger.error(f"Failed to check cluster momentum: {e}")
            return False
    
    def _create_jira_issue(self, feedback: Feedback):
        """Create JIRA issue for high-priority feedback."""
        try:
            # Check if initiative already exists for this cluster
            existing_initiative = None
            if feedback.cluster_id:
                existing_initiative = self.db.query(Initiative).filter(
                    Initiative.cluster_id == feedback.cluster_id
                ).first()
            
            if existing_initiative:
                # Update existing initiative
                self._update_jira_issue(existing_initiative, feedback)
            else:
                # Create new initiative
                self._create_new_initiative(feedback)
                
        except Exception as e:
            logger.error(f"Failed to create JIRA issue: {e}")
    
    def _create_new_initiative(self, feedback: Feedback):
        """Create new initiative and JIRA issue."""
        try:
            # Generate summary and description
            summary = self._generate_jira_summary(feedback)
            description = self._generate_jira_description(feedback)
            
            # Create initiative record
            initiative = Initiative(
                title=summary,
                description=description,
                status='new',
                cluster_id=feedback.cluster_id
            )
            self.db.add(initiative)
            self.db.commit()
            
            # Create JIRA issue
            if self.jira_enabled:
                jira_key = self._create_jira_epic(summary, description)
                if jira_key:
                    initiative.jira_key = jira_key
                    self.db.commit()
                    logger.info(f"Created JIRA epic {jira_key} for initiative {initiative.id}")
            
        except Exception as e:
            logger.error(f"Failed to create new initiative: {e}")
            raise
    
    def _update_jira_issue(self, initiative: Initiative, feedback: Feedback):
        """Update existing JIRA issue with new feedback."""
        try:
            if not self.jira_enabled or not initiative.jira_key:
                return
            
            # Add comment to existing JIRA issue
            comment = self._generate_jira_comment(feedback)
            self._add_jira_comment(initiative.jira_key, comment)
            
            # Update labels and severity if needed
            self._update_jira_labels(initiative.jira_key, feedback)
            
            logger.info(f"Updated JIRA issue {initiative.jira_key} with feedback {feedback.id}")
            
        except Exception as e:
            logger.error(f"Failed to update JIRA issue: {e}")
    
    def _generate_jira_summary(self, feedback: Feedback) -> str:
        """Generate JIRA epic summary."""
        if feedback.cluster_id:
            cluster = self.db.query(Cluster).filter(Cluster.id == feedback.cluster_id).first()
            if cluster and cluster.summary:
                return f"Feedback: {cluster.summary[:100]}..."
        
        # Fallback to feedback text
        return f"Feedback: {feedback.text_clean[:100] if feedback.text_clean else feedback.text_raw[:100]}..."
    
    def _generate_jira_description(self, feedback: Feedback) -> str:
        """Generate JIRA epic description."""
        description = f"""
Feedback from {feedback.source} (Priority: {feedback.priority_score:.2f})

Original text: {feedback.text_raw}

Clean text: {feedback.text_clean or 'Not available'}

Source: {feedback.source}
Author: {feedback.author_id}
Created: {feedback.created_at}
        """.strip()
        
        # Add cluster info if available
        if feedback.cluster_id:
            cluster = self.db.query(Cluster).filter(Cluster.id == feedback.cluster_id).first()
            if cluster:
                description += f"\n\nCluster: {cluster.summary}"
                description += f"\nCluster size: {cluster.size}"
        
        return description
    
    def _generate_jira_comment(self, feedback: Feedback) -> str:
        """Generate JIRA comment for additional feedback."""
        return f"""
Additional feedback from {feedback.source}:
{feedback.text_raw}

Priority: {feedback.priority_score:.2f}
        """.strip()
    
    def _create_jira_epic(self, summary: str, description: str) -> Optional[str]:
        """Create JIRA epic via REST API."""
        if not self.jira_enabled:
            return None
        
        try:
            url = f"{self.jira_base_url}/rest/api/2/issue"
            
            payload = {
                "fields": {
                    "project": {"key": "FEEDBACK"},  # Configure as needed
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": "Epic"},
                    "priority": {"name": "High"}
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                auth=(self.jira_username, self.jira_api_token),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                result = response.json()
                return result.get("key")
            else:
                logger.error(f"Failed to create JIRA issue: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create JIRA epic: {e}")
            return None
    
    def _add_jira_comment(self, jira_key: str, comment: str):
        """Add comment to JIRA issue."""
        try:
            url = f"{self.jira_base_url}/rest/api/2/issue/{jira_key}/comment"
            
            payload = {"body": comment}
            
            response = requests.post(
                url,
                json=payload,
                auth=(self.jira_username, self.jira_api_token),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 201:
                logger.error(f"Failed to add JIRA comment: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to add JIRA comment: {e}")
    
    def _update_jira_labels(self, jira_key: str, feedback: Feedback):
        """Update JIRA issue labels."""
        try:
            # Get labels for feedback
            labels = self.db.query(Label).join(FeedbackLabel).filter(
                FeedbackLabel.feedback_id == feedback.id
            ).all()
            
            if not labels:
                return
            
            # Convert to JIRA label format
            jira_labels = [label.name.replace('/', '-') for label in labels]
            
            # Update JIRA issue
            url = f"{self.jira_base_url}/rest/api/2/issue/{jira_key}"
            
            payload = {
                "fields": {
                    "labels": jira_labels
                }
            }
            
            response = requests.put(
                url,
                json=payload,
                auth=(self.jira_username, self.jira_api_token),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 204:
                logger.error(f"Failed to update JIRA labels: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to update JIRA labels: {e}")
    
    def run(self):
        """Main worker loop."""
        logger.info("Starting actions worker...")
        
        while True:
            try:
                # Process feedback that needs actions
                actionable_feedback = self.db.query(Feedback).filter(
                    and_(
                        Feedback.status == 'new',
                        Feedback.priority_score.isnot(None)
                    )
                ).limit(10).all()
                
                for feedback in actionable_feedback:
                    self.process_actions(feedback.id)
                
                # Sleep if no work
                if not actionable_feedback:
                    import time
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                logger.info("Stopping actions worker...")
                break
            except Exception as e:
                logger.error(f"Error in actions worker: {e}")
                continue
        
        self.db.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'db'):
            self.db.close() 