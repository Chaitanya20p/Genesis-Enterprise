"""
============================================================
 Genesis AI — SQLAlchemy Database Models (models.py)
 Defines the persistent data structures for Project Memory.
============================================================
"""

from datetime import datetime
from app import db


class Project(db.Model):
    """
    Stores each Genesis AI orchestration run as a named project.
    Acts as the top-level container for all agent outputs.
    """
    __tablename__ = "projects"

    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(256), nullable=False)
    problem_stmt  = db.Column(db.Text, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    # JSON blob storing the full orchestration result (all three solutions)
    result_json   = db.Column(db.Text, nullable=True)
    # Comma-separated paths to uploaded RAG documents
    rag_docs      = db.Column(db.Text, nullable=True)

    # Relationship: one project can have many debate log entries
    debate_logs   = db.relationship("DebateLog", backref="project", lazy=True)

    def to_dict(self):
        return {
            "id":           self.id,
            "title":        self.title,
            "problem_stmt": self.problem_stmt,
            "created_at":   self.created_at.isoformat(),
            "result_json":  self.result_json,
        }


class DebateLog(db.Model):
    """
    Records individual turns in the AI Debate Room.
    Each turn belongs to a project and carries a speaker label
    (e.g. 'Architect', 'Security', 'Finance') and the message text.
    """
    __tablename__ = "debate_logs"

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    speaker     = db.Column(db.String(64), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    round_num   = db.Column(db.Integer, default=1)   # Debate iteration number
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "project_id": self.project_id,
            "speaker":    self.speaker,
            "message":    self.message,
            "round":      self.round_num,
            "timestamp":  self.timestamp.isoformat(),
        }
