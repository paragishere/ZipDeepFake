from . import db
from datetime import datetime

class VideoLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    result = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)