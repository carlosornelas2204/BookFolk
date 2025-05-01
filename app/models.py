from datetime import datetime
from flask_login import UserMixin
from . import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    reviews = db.relationship('Review', back_populates='user')
    owned_clubs = db.relationship('Club', back_populates='owner', cascade='all, delete-orphan')
    club_memberships = db.relationship('ClubMember', back_populates='user', cascade='all, delete-orphan')

    def get_pending_invites_count(self):
        return ClubInvite.query.filter_by(
            user_id=self.id,
            status='pending'
        ).count()

    def get_pending_invites(self):
        return ClubInvite.query.filter_by(
            user_id=self.id,
            status='pending'
        ).all()

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password, password)


class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    open_library_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    cover_i = db.Column(db.String(50))
    reviews = db.relationship('Review', back_populates='book')
    genre = db.Column(db.String(50), nullable=False, default='Geral')
    isbn = db.Column(db.String(20))

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    date_rated = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=True)  # Sempre True pois só cria ao marcar como lido

    user = db.relationship('User', back_populates='reviews')
    book = db.relationship('Book', back_populates='reviews')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='_user_book_uc'),
    )


class Club(db.Model):
    __tablename__ = 'clubs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    max_members = db.Column(db.Integer, nullable=False)
    current_phase = db.Column(db.String(20), default='forming')  # forming, choosing, reading, completed
    current_cycle = db.Column(db.Integer, default=1)

    owner = db.relationship('User', back_populates='owned_clubs')
    members = db.relationship('ClubMember', back_populates='club', cascade='all, delete-orphan')
    topics = db.relationship('ClubTopic', back_populates='club', cascade='all, delete-orphan')


class ClubMember(db.Model):
    __tablename__ = 'club_members'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'))
    join_date = db.Column(db.DateTime, default=datetime.utcnow)

    club = db.relationship('Club', back_populates='members')
    user = db.relationship('User', back_populates='club_memberships')
    book = db.relationship('Book')


class ClubTopic(db.Model):
    __tablename__ = 'club_topics'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    cycle = db.Column(db.Integer, default=1)

    club = db.relationship('Club', back_populates='topics')
    book = db.relationship('Book')
    messages = db.relationship('ClubMessage', back_populates='topic', cascade='all, delete-orphan')


class ClubMessage(db.Model):
    __tablename__ = 'club_messages'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('club_topics.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    topic = db.relationship('ClubTopic', back_populates='messages')
    user = db.relationship('User')

class ClubInvite(db.Model):
    __tablename__ = 'club_invites'
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    club = db.relationship('Club')
    user = db.relationship('User', foreign_keys=[user_id])
    sender = db.relationship('User', foreign_keys=[sender_id])


class RecommendationHistory(db.Model):
    __tablename__ = 'recommendation_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='recommendation_history')
    book = db.relationship('Book')