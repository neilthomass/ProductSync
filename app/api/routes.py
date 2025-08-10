from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from app.models.database import get_db, SessionLocal
from app.models.feedback import Feedback, FeedbackLabel
from app.models.cluster import Cluster
from app.models.initiative import Initiative
from app.models.label import Label
from app.models.product_area import ProductArea
from app.nlp.preprocessor import TextPreprocessor
from app.nlp.classifier import TextClassifier
from app.nlp.embedder import TextEmbedder
import json
import os
import logging
from datetime import datetime
import hmac
import hashlib

logger = logging.getLogger(__name__)

# Create blueprints
feedback_bp = Blueprint('feedback', __name__)
slack_bp = Blueprint('slack', __name__)
discord_bp = Blueprint('discord', __name__)
notion_bp = Blueprint('notion', __name__)

# Slack verification
def verify_slack_request(request):
    """Verify Slack request signature."""
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    if not slack_signing_secret:
        return True  # Skip verification if not configured
    
    timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
    signature = request.headers.get('X-Slack-Signature', '')
    
    if not timestamp or not signature:
        return False
    
    # Check if request is too old (5 minutes)
    if abs(int(datetime.now().timestamp()) - int(timestamp)) > 300:
        return False
    
    # Verify signature
    sig_basestring = f"v0:{timestamp}:{request.get_data().decode('utf-8')}"
    expected_signature = f"v0={hmac.new(slack_signing_secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()}"
    
    return hmac.compare_digest(signature, expected_signature)

# Feedback routes
@feedback_bp.route('/', methods=['GET'])
def get_feedback():
    """Get feedback with filters."""
    try:
        db = next(get_db())
        
        # Parse filters
        source = request.args.get('source')
        status = request.args.get('status')
        product_area = request.args.get('product_area')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        query = db.query(Feedback)
        
        if source:
            query = query.filter(Feedback.source == source)
        if status:
            query = query.filter(Feedback.status == status)
        if product_area:
            query = query.join(ProductArea).filter(ProductArea.name == product_area)
        
        feedback_list = query.offset(offset).limit(limit).all()
        
        result = []
        for fb in feedback_list:
            fb_data = {
                'id': fb.id,
                'source': fb.source,
                'author_id': fb.author_id,
                'created_at': fb.created_at.isoformat() if fb.created_at else None,
                'text_raw': fb.text_raw,
                'text_clean': fb.text_clean,
                'priority_score': fb.priority_score,
                'status': fb.status,
                'cluster_id': fb.cluster_id
            }
            
            # Add labels
            labels = db.query(Label).join(FeedbackLabel).filter(
                FeedbackLabel.feedback_id == fb.id
            ).all()
            fb_data['labels'] = [{'name': l.name, 'type': l.type} for l in labels]
            
            result.append(fb_data)
        
        return jsonify({
            'feedback': result,
            'total': len(result),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Failed to get feedback: {e}")
        return jsonify({'error': 'Failed to retrieve feedback'}), 500

@feedback_bp.route('/<int:feedback_id>', methods=['GET'])
def get_feedback_by_id(feedback_id):
    """Get specific feedback by ID."""
    try:
        db = next(get_db())
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        
        if not feedback:
            return jsonify({'error': 'Feedback not found'}), 404
        
        # Get labels
        labels = db.query(Label).join(FeedbackLabel).filter(
            FeedbackLabel.feedback_id == feedback.id
        ).all()
        
        result = {
            'id': feedback.id,
            'source': feedback.source,
            'source_msg_id': feedback.source_msg_id,
            'author_id': feedback.author_id,
            'created_at': feedback.created_at.isoformat() if feedback.created_at else None,
            'text_raw': feedback.text_raw,
            'text_clean': feedback.text_clean,
            'priority_score': feedback.priority_score,
            'status': feedback.status,
            'cluster_id': feedback.cluster_id,
            'labels': [{'name': l.name, 'type': l.type} for l in labels]
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to get feedback {feedback_id}: {e}")
        return jsonify({'error': 'Failed to retrieve feedback'}), 500

@feedback_bp.route('/<int:feedback_id>/resolve', methods=['POST'])
def resolve_feedback(feedback_id):
    """Resolve feedback (human override)."""
    try:
        db = next(get_db())
        data = request.get_json()
        
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            return jsonify({'error': 'Feedback not found'}), 404
        
        # Update status
        feedback.status = 'resolved'
        
        # Update labels if provided
        if 'labels' in data:
            # Remove existing labels
            db.query(FeedbackLabel).filter(FeedbackLabel.feedback_id == feedback_id).delete()
            
            # Add new labels
            for label_name in data['labels']:
                label = db.query(Label).filter(Label.name == label_name).first()
                if label:
                    feedback_label = FeedbackLabel(
                        feedback_id=feedback_id,
                        label_id=label.id,
                        score=1.0  # Human override = high confidence
                    )
                    db.add(feedback_label)
        
        # Update product area if provided
        if 'product_area' in data:
            product_area = db.query(ProductArea).filter(ProductArea.name == data['product_area']).first()
            if product_area:
                feedback.product_area_id = product_area.id
        
        db.commit()
        
        return jsonify({'message': 'Feedback resolved successfully'})
        
    except Exception as e:
        logger.error(f"Failed to resolve feedback {feedback_id}: {e}")
        return jsonify({'error': 'Failed to resolve feedback'}), 500

# Slack routes
@slack_bp.route('/events', methods=['POST'])
def slack_events():
    """Handle Slack Events API as specified in README."""
    try:
        # Verify request
        if not verify_slack_request(request):
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.get_json()
        
        # Handle URL verification
        if data.get('type') == 'url_verification':
            return jsonify({'challenge': data.get('challenge')})
        
        # Handle events
        event = data.get('event', {})
        if event.get('type') == 'message' and 'subtype' not in event:
            # Create feedback payload
            payload = {
                'source': 'slack',
                'source_msg_id': event.get('ts'),
                'author_id': event.get('user'),
                'text': event.get('text', ''),
                'channel': event.get('channel'),
                'created_at': datetime.fromtimestamp(float(event.get('ts', 0))).isoformat()
            }
            
            # Push to Redis queue
            import redis
            redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            
            # Check for duplicate
            key = f"dupe:slack:{event['ts']}"
            if redis_client.setnx(key, 1):
                redis_client.expire(key, 7 * 24 * 3600)  # 7 days
                redis_client.lpush("ingest:feedback", json.dumps(payload))
                logger.info(f"Queued Slack feedback from channel {payload['channel']}")
            else:
                logger.info(f"Duplicate Slack feedback detected: {key}")
        
        return jsonify({'ok': True})
        
    except Exception as e:
        logger.error(f"Failed to process Slack event: {e}")
        return jsonify({'error': 'Failed to process event'}), 500

# Discord routes
@discord_bp.route('/webhook', methods=['POST'])
def discord_webhook():
    """Handle Discord webhook as specified in README."""
    try:
        data = request.get_json()
        
        # Create feedback payload
        payload = {
            'source': 'discord',
            'source_msg_id': str(data.get('id')),
            'author_id': str(data.get('author', {}).get('id')),
            'text': data.get('content', ''),
            'channel': str(data.get('channel_id')),
            'created_at': data.get('timestamp')
        }
        
        # Push to Redis queue
        import redis
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        
        # Check for duplicate
        key = f"dupe:discord:{data.get('id')}"
        if redis_client.setnx(key, 1):
            redis_client.expire(key, 7 * 24 * 3600)  # 7 days
            redis_client.lpush("ingest:feedback", json.dumps(payload))
            logger.info(f"Queued Discord feedback from channel {payload['channel']}")
        else:
            logger.info(f"Duplicate Discord feedback detected: {key}")
        
        return jsonify({'ok': True})
        
    except Exception as e:
        logger.error(f"Failed to process Discord webhook: {e}")
        return jsonify({'error': 'Failed to process webhook'}), 500

# Notion routes
@notion_bp.route('/pull', methods=['POST'])
def notion_pull():
    """Handle Notion feedback pull as specified in README."""
    try:
        data = request.get_json()
        
        # This would typically be a scheduled job that queries Notion API
        # For now, accept manual pushes
        feedback_items = data.get('feedback', [])
        
        import redis
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        
        for item in feedback_items:
            payload = {
                'source': 'notion',
                'source_msg_id': str(item.get('page_id')),
                'author_id': item.get('author', 'unknown'),
                'text': f"{item.get('title', '')}\n{item.get('rich_text', '')}",
                'created_at': item.get('created_time')
            }
            
            # Check for duplicate
            key = f"dupe:notion:{item.get('page_id')}"
            if redis_client.setnx(key, 1):
                redis_client.expire(key, 7 * 24 * 3600)  # 7 days
                redis_client.lpush("ingest:feedback", json.dumps(payload))
                logger.info(f"Queued Notion feedback: {item.get('title', '')}")
            else:
                logger.info(f"Duplicate Notion feedback detected: {key}")
        
        return jsonify({'message': f'Processed {len(feedback_items)} feedback items'})
        
    except Exception as e:
        logger.error(f"Failed to process Notion pull: {e}")
        return jsonify({'error': 'Failed to process Notion pull'}), 500

# JIRA sync route
@feedback_bp.route('/jira/sync', methods=['POST'])
def jira_sync():
    """Sync JIRA status updates."""
    try:
        db = next(get_db())
        data = request.get_json()
        
        # This would typically sync from JIRA to update initiative statuses
        # For now, accept manual updates
        for update in data.get('updates', []):
            jira_key = update.get('jira_key')
            status = update.get('status')
            
            if jira_key and status:
                initiative = db.query(Initiative).filter(Initiative.jira_key == jira_key).first()
                if initiative:
                    initiative.status = status
                    db.commit()
                    logger.info(f"Updated initiative {initiative.id} status to {status}")
        
        return jsonify({'message': 'JIRA sync completed'})
        
    except Exception as e:
        logger.error(f"Failed to sync JIRA: {e}")
        return jsonify({'error': 'Failed to sync JIRA'}), 500 
