from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID


from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from datetime import datetime
import uuid
import os


from myApp import app

# Configure the SQLite database
dbname = "mydatabase.db"
should_create = "RECREATE_DB" in os.environ

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{dbname}'
db = SQLAlchemy(app)

# Define a User model
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)  # Added phone_number field
    name = db.Column(db.String(80), unique=True, nullable=True)
    status = db.Column(db.String(255), nullable=True)  # Added status field
    last_seen = db.Column(db.TIMESTAMP, default=datetime.utcnow)  # Added last_seen field
    is_ok = db.Column(db.Boolean, default=True)  # Added isOk field

    def __repr__(self):
        return f'<User {self.phone_number} / {self.name}>'


class Group(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=True)
    additional_data = db.Column(JSON, nullable=True)
    owner_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    owner = relationship('User', foreign_keys=[owner_id], backref='owner_of_groups')
    users = relationship('User', secondary='group_users', backref='groups')
    admins = relationship('User', secondary='group_admins', backref='admin_of_groups')
    viewers = relationship('User', secondary='group_viewers', backref='viewer_of_groups')
    def __repr__(self):
        return f'<Group {self.name} by {self.owner and self.owner.name or "n/a"}>'


class GroupUsers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)

class GroupAdmins(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)

class GroupViewers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)


if should_create:
	with app.app_context():
		db.create_all()
