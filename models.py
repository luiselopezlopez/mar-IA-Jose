from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    user_type = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        """Return True if the user has administrator privileges."""
        try:
            return int(self.user_type or 1) == 0
        except (TypeError, ValueError):  # Fallback for unexpected values
            return False
    
    def __repr__(self):
        return f'<User {self.username}>'

class Chat(db.Model):
    """Chat model to store chat information"""
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200))
    system_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with User model
    user = db.relationship('User', backref=db.backref('chats', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Chat {self.title}>'

class Message(db.Model):
    """Message model to store chat messages"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(36), db.ForeignKey('chat.id'))
    role = db.Column(db.String(20))  # 'user' or 'assistant'
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with Chat model
    chat = db.relationship('Chat', backref=db.backref('messages', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<Message {self.id} - {self.role}>'

class File(db.Model):
    """File model to store uploaded files"""
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    filename = db.Column(db.String(255))
    file_hash = db.Column(db.String(32), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with User model
    user = db.relationship('User', backref=db.backref('files', lazy='dynamic'))
    
    def __repr__(self):
        return f'<File {self.filename}>'


class UserPrompt(db.Model):
    """User-scoped prompt catalog entries for system message presets."""
    __tablename__ = 'user_prompts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('prompts', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_user_prompt_name'),
    )

    def __repr__(self):
        return f'<UserPrompt {self.name}>'