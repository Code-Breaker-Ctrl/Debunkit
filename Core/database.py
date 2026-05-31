from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

db = SQLAlchemy()

class Analysis(db.Model):
    """
    Store all fact-check analyses performed by users.
    """
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Input
    text_analyzed = db.Column(db.Text, nullable=False, index=True)
    
    # Results
    verdict = db.Column(db.String(50), nullable=False, index=True)  
    confidence = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text)
    fact_check = db.Column(db.Text)
    
    # Details
    red_flags = db.Column(JSON)  
    sources = db.Column(JSON)    
    mode = db.Column(db.String(50))
    
    # Metadata
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<Analysis {self.id}: {self.verdict} ({self.confidence}%)>'
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'text_analyzed': self.text_analyzed,
            'verdict': self.verdict,
            'confidence': self.confidence,
            'reason': self.reason,
            'fact_check': self.fact_check,
            'red_flags': self.red_flags or [],
            'sources': self.sources or [],
            'mode': self.mode,
            'timestamp': self.timestamp.isoformat()
        }

def init_db(app):
    """Initialize database with Flask app."""
    db.init_app(app)
    
    with app.app_context():
        logger.info("Creating database tables...")
        db.create_all()
        logger.info("[OK] Database initialized successfully")

def save_analysis(text, verdict, confidence, reason, fact_check, red_flags, sources, mode, user, request):
    """Save analysis result to database."""
    try:
        analysis = Analysis(
            user_id=user.id,
            text_analyzed=text[:5000],
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            fact_check=fact_check,
            red_flags=red_flags,
            sources=sources,
            mode=mode,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        logger.info(f"[OK] Saved analysis #{analysis.id} for user {user.username}")
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to save analysis: {e}")
        db.session.rollback()
        return None

def get_analysis_history(user=None, limit=50, offset=0):
    """Get recent analyses for a user."""
    try:
        query = Analysis.query
        if user:
            query = query.filter_by(user_id=user.id)
        
        analyses = query.order_by(Analysis.timestamp.desc()).limit(limit).offset(offset).all()
        return [a.to_dict() for a in analyses]
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []

def get_analysis_by_id(analysis_id):
    """Get specific analysis by ID."""
    try:
        analysis = Analysis.query.get(analysis_id)
        return analysis.to_dict() if analysis else None
    except Exception as e:
        logger.error(f"Failed to fetch analysis: {e}")
        return None

def search_analyses(query, user=None, limit=50):
    """Search analyses by text content."""
    try:
        q = Analysis.query
        if user:
            q = q.filter_by(user_id=user.id)
        
        results = q.filter(
            Analysis.text_analyzed.ilike(f'%{query}%')
        ).order_by(Analysis.timestamp.desc()).limit(limit).all()
        
        return [a.to_dict() for a in results]
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def get_statistics(user=None):
    """Get accuracy statistics."""
    try:
        q = Analysis.query
        if user:
            q = q.filter_by(user_id=user.id)
        
        total = q.count()
        
        if total == 0:
            return {
                'total_analyses': 0,
                'verdict_breakdown': {},
                'average_confidence': 0,
                'mode_breakdown': {}
            }
        
        verdicts = q.with_entities(
            Analysis.verdict,
            func.count(Analysis.id)
        ).group_by(Analysis.verdict).all()
        
        modes = q.with_entities(
            Analysis.mode,
            func.count(Analysis.id)
        ).group_by(Analysis.mode).all()
        
        avg_confidence = q.with_entities(
            func.avg(Analysis.confidence)
        ).scalar() or 0
        
        return {
            'total_analyses': total,
            'verdict_breakdown': {verdict: count for verdict, count in verdicts},
            'average_confidence': round(float(avg_confidence), 2),
            'mode_breakdown': {mode: count for mode, count in modes}
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return {}

def clear_old_analyses(days=30):
    """Delete analyses older than specified days."""
    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted = Analysis.query.filter(Analysis.timestamp < cutoff).delete()
        db.session.commit()
        
        logger.info(f"Deleted {deleted} old analyses")
        return deleted
    except Exception as e:
        logger.error(f"Failed to delete old analyses: {e}")
        return 0