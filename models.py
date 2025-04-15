# models.py
from datetime import datetime, timezone
from extensions import db, bcrypt # Import từ extensions
from flask_login import UserMixin
from sqlalchemy import Date

# --- Bảng liên kết ---
idea_recipient_lecturers = db.Table('idea_recipient_lecturers',
    db.Column('student_idea_id', db.Integer, db.ForeignKey('student_idea.id', ondelete='CASCADE'), primary_key=True),
    db.Column('lecturer_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
)

student_topic_interest = db.Table('student_topic_interest',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), primary_key=True)
)

# --- Model User ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(128), nullable=False, default='default.jpg')
    gender = db.Column(db.String(10), nullable=True)
    password_hash = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')
    class_name = db.Column(db.String(50), nullable=True)
    date_of_birth = db.Column(Date, nullable=True)

    phone_number = db.Column(db.String(20), unique=False, nullable=True) # Đã sửa unique=False
    contact_email = db.Column(db.String(120), unique=True, nullable=True)
    about_me = db.Column(db.Text, nullable=True)

    # Relationships
    # <<< Chỉ giữ lại MỘT posts relationship >>>
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')

    # <<< Sửa lại relationship dùng back_populates >>>
    interested_topics = db.relationship('Post', secondary=student_topic_interest, lazy='dynamic',
                                         back_populates='interested_students') # <<< Sửa thành back_populates

    # <<< Sửa lại relationship dùng back_populates >>>
    received_ideas = db.relationship('StudentIdea', secondary=idea_recipient_lecturers, lazy='dynamic',
                                     back_populates='recipients') # <<< Sửa thành back_populates

    ideas_submitted = db.relationship('StudentIdea', backref='student', lazy='dynamic',
                                      foreign_keys='StudentIdea.student_id', cascade='all, delete-orphan')

    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic',
                                    foreign_keys='Notification.recipient_id',
                                    order_by='Notification.timestamp.desc()',
                                    cascade='all, delete-orphan')

    def set_password(self, password):
        """Tạo password hash."""
        # Đảm bảo bcrypt đã được import đúng
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
            """Kiểm tra password hash."""
            # Đảm bảo bcrypt đã được import đúng
            return bcrypt.check_password_hash(self.password_hash, password)


# === Model Post ===
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    content = db.Column(db.Text, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    post_type = db.Column(db.String(10), nullable=False, default='article')
    status = db.Column(db.String(20), nullable=True, default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False) # Sửa ondelete nếu cần

    attachments = db.relationship('Attachment', backref='post', lazy=True, cascade='all, delete-orphan')

    # <<< THÊM RELATIONSHIP NGƯỢC LẠI interested_students >>>
    interested_students = db.relationship('User', secondary=student_topic_interest, lazy='dynamic',
                                          back_populates='interested_topics') # Trỏ đến thuộc tính trong User
    # <<< KẾT THÚC THÊM >>>


    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"


# === Model Attachment ===
class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(150), nullable=False)
    saved_filename = db.Column(db.String(100), unique=True, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    def __repr__(self): ... # Giữ nguyên


# === Model StudentIdea ===
class StudentIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default='pending')
    feedback = db.Column(db.Text, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    attachments = db.relationship('IdeaAttachment', backref='idea', lazy=True, cascade='all, delete-orphan')

    # <<< SỬA LẠI RELATIONSHIP NÀY DÙNG back_populates >>>
    recipients = db.relationship('User', secondary=idea_recipient_lecturers, lazy='dynamic',
                                 back_populates='received_ideas') # Trỏ đến thuộc tính trong User
    # <<< KẾT THÚC SỬA >>>

    def __repr__(self): ... # Giữ nguyên


# === Model IdeaAttachment ===
class IdeaAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(150), nullable=False)
    saved_filename = db.Column(db.String(100), unique=True, nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('student_idea.id', ondelete='CASCADE'), nullable=False)
    def __repr__(self): ... # Giữ nguyên


# === Model Notification ===
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    related_idea_id = db.Column(db.Integer, db.ForeignKey('student_idea.id', ondelete='SET NULL'), nullable=True)
    # related_post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='SET NULL'), nullable=True)
    def __repr__(self): ... # Giữ nguyên




