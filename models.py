
from myApp import app


from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON, select
from sqlalchemy.orm import relationship

from datetime import datetime, timedelta
import uuid
import os
import statistics

# Configure the SQLite database
# dbname = "mydatabase.db"
# should_create = "RECREATE_DB" in os.environ

#app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{dbname}'

db = SQLAlchemy(app)

class Friendship(db.Model):
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), primary_key=True)
    friend_id = db.Column(db.String(36), db.ForeignKey('user.id'), primary_key=True)


# Define a User model
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)  # Added phone_number field
    name = db.Column(db.String(80), unique=False, nullable=True)
    status = db.Column(db.String(255), nullable=True)  # Added status field
    last_seen = db.Column(db.TIMESTAMP, default=datetime.utcnow)  # Added last_seen field
    prev_seen = db.Column(db.TIMESTAMP, default=datetime.utcnow)  # The event before the last seen
    is_ok = db.Column(db.Boolean, default=True)  # Added isOk field
 
   # Define a many-to-many relationship for mutual friendships
    my_friends = db.relationship(
        'User',
        secondary='friendship',
        primaryjoin=(id == Friendship.user_id),
        secondaryjoin=(id == Friendship.friend_id),
    )
    @property
    def friends(self):
        friend_ids = [friend.id for friend in self.my_friends]
        friend_ids += [friend.id for friend in User.query.filter(User.my_friends.any(id=self.id))]
        return self.query.filter(User.id.in_(friend_ids))

    def add_friend(self, friend):
        if friend not in self.my_friends:
            self.my_friends.append(friend)

    def get_status_score(self, timestamp):
        print("A")
        print(repr(self.last_seen))
        print(repr(timestamp))
        if self.is_ok and self.last_seen >= (timestamp - timedelta(minutes=1)): 
            print(10)
            return 10
        elif self.is_ok:
            print(5)
            return 5
        else:
            print(0)
            return 0

    def __repr__(self):
        return f'<User {self.phone_number} / {self.name}>'

class Group(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=False, nullable=True)
    additional_data = db.Column(JSON, nullable=True)
    owner_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    owner = relationship('User', foreign_keys=[owner_id], backref='owner_of_groups')
    users = relationship('User', secondary='group_users', backref='groups')
    admins = relationship('User', secondary='group_admins', backref='admin_of_groups')
    viewers = relationship('User', secondary='group_viewers', backref='viewer_of_groups')
    def __repr__(self):
        return f'<Group {self.name} by {self.owner and self.owner.name or "n/a"}>'

    def get_last_event_time(self):
        # Extract last_seen timestamps of all users in the group
        last_seen_timestamps = [user.last_seen for user in self.users]
        return sorted(last_seen_timestamps)[:1][-1]
        if not last_seen_timestamps:
            return datetime.min  # No users in the group, cannot determine last event time

        # Sort the timestamps in ascending order
        sorted_timestamps = sorted(last_seen_timestamps)

        # Calculate time differences between consecutive timestamps
        time_diffs = [(b - a).total_seconds() for a, b in zip(sorted_timestamps, sorted_timestamps[1:])]

        # Calculate a measure of central tendency (e.g., median)
        central_tendency = statistics.median(time_diffs)

        burst_start_timestamps = [timestamp1 for timestamp1, timestamp2 in zip(sorted_timestamps, sorted_timestamps[1:])
                           if (timestamp2 - timestamp1).total_seconds() < central_tendency * 0.5]


        # Find the minimal timestamp within the last burst
        last_burst_min_timestamp = min(burst_start_timestamps, default=None)

        return last_burst_min_timestamp - timedelta(minutes=1)

    def get_status_score(self):
        timestamp = self.get_last_event_time()
        return min([u.get_status_score(timestamp=timestamp) for u in self.users])

    def count_score(self,score):
        timestamp = self.get_last_event_time()
        return sum(1 for u in self.users if u.get_status_score(timestamp=timestamp) == score)


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

# if should_create:
#   with app.app_context():
#       db.create_all()
