# models.py
from datetime import datetime, timezone
from extensions import db, bcrypt  # Import từ extensions
from flask_login import UserMixin
from sqlalchemy import Date

# --- Bảng liên kết ---
# Bảng liên kết Giảng viên nhận Ý tưởng của Sinh viên
idea_recipient_lecturers = db.Table('idea_recipient_lecturers',
                                    db.Column('student_idea_id', db.Integer,
                                              db.ForeignKey('student_idea.id', ondelete='CASCADE'), primary_key=True),
                                    db.Column('lecturer_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                                              primary_key=True)
                                    )

# Bảng liên kết Sinh viên quan tâm Đề tài (Post)
student_topic_interest = db.Table('student_topic_interest',
                                  db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                                            primary_key=True),
                                  db.Column('post_id', db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'),
                                            primary_key=True)
                                  )

# Bảng liên kết Bài đăng (Post) và Thẻ (Tag)
# (Đã di chuyển ra khỏi User class)
post_tags = db.Table('post_tags',
                     db.Column('post_id', db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), primary_key=True),
                     db.Column('tag_id', db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True)
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

    phone_number = db.Column(db.String(20), unique=False, nullable=True)
    contact_email = db.Column(db.String(120), unique=True, nullable=True)
    about_me = db.Column(db.Text, nullable=True)

    # --- Relationships ---
    # Bài đăng của người dùng (Tác giả)
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')



    # Các ý tưởng mà người dùng (Giảng viên) nhận được
    received_ideas = db.relationship('StudentIdea', secondary=idea_recipient_lecturers, lazy='dynamic',
                                     back_populates='recipients')

    # Các ý tưởng mà người dùng (Sinh viên) đã gửi
    ideas_submitted = db.relationship('StudentIdea', backref='student', lazy='dynamic',
                                      foreign_keys='StudentIdea.student_id', cascade='all, delete-orphan')

    # Các thông báo mà người dùng nhận được
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic',
                                    foreign_keys='Notification.recipient_id',
                                    order_by='Notification.timestamp.desc()',
                                    cascade='all, delete-orphan')

    # (Không cần định nghĩa post_tags và Tag ở đây nữa)

    # --- Methods ---
    def set_password(self, password):
        """Tạo password hash."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Kiểm tra password hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.full_name}', '{self.email}', '{self.role}')"


# --- Model Tag ---
# (Đã di chuyển ra khỏi User class và đặt trước Post class)
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Relationship 'posts' sẽ được tạo tự động bởi backref từ Post model

    def __repr__(self):
        return f'<Tag {self.name}>'


# === Model Post ===
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    content = db.Column(db.Text, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    post_type = db.Column(db.String(10), nullable=False, default='article')
    status = db.Column(db.String(20), nullable=True, default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    # --- Relationships ---
    attachments = db.relationship('Attachment', backref='post', lazy=True, cascade='all, delete-orphan')

    # Relationship với Tag (Tham chiếu đến 'Tag' và 'post_tags' đã định nghĩa ở trên)
    tags = db.relationship('Tag', secondary=post_tags, lazy='dynamic',
                           backref=db.backref('posts', lazy='dynamic'))

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"


# === Model Attachment ===
class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(150), nullable=False)
    saved_filename = db.Column(db.String(100), unique=True, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f"Attachment('{self.original_filename}', Post ID: {self.post_id})"


# === Model StudentIdea ===
class StudentIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default='pending')
    feedback = db.Column(db.Text, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    # --- Relationships ---
    attachments = db.relationship('IdeaAttachment', backref='idea', lazy=True, cascade='all, delete-orphan')

    recipients = db.relationship('User', secondary=idea_recipient_lecturers, lazy='dynamic',
                                 back_populates='received_ideas')

    def __repr__(self):
        return f"StudentIdea('{self.title}', Status: {self.status})"


# === Model IdeaAttachment ===
class IdeaAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(150), nullable=False)
    saved_filename = db.Column(db.String(100), unique=True, nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('student_idea.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f"IdeaAttachment('{self.original_filename}', Idea ID: {self.idea_id})"


# === Model Notification ===
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    related_idea_id = db.Column(db.Integer, db.ForeignKey('student_idea.id', ondelete='SET NULL'), nullable=True)
    # Giả sử bạn đã thêm các trường này ở bước trước
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"Notification('{self.content[:30]}...', Read: {self.is_read})"


class TopicApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # Trạng thái đơn đăng ký: pending, accepted, rejected
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    # (Tùy chọn) Lời nhắn của sinh viên khi đăng ký
    message = db.Column(db.Text, nullable=True)

    # Khóa ngoại đến sinh viên đăng ký
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    # Khóa ngoại đến bài đăng/đề tài được đăng ký
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)

    # --- Relationships ---
    # Liên kết đến người dùng (sinh viên)
    student = db.relationship('User', backref=db.backref('topic_applications', lazy='dynamic'))
    # Liên kết đến bài đăng (đề tài)
    topic = db.relationship('Post', backref=db.backref('applications', lazy='dynamic'))

    # --- Ràng buộc duy nhất ---
    # Đảm bảo một sinh viên chỉ đăng ký một đề tài một lần
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='uq_user_post_application'),)

    def __repr__(self):
        return f'<TopicApplication User {self.user_id} -> Post {self.post_id} ({self.status})>'




# === Model AcademicWork ===
# Model lưu thông tin các công trình học thuật tiêu biểu (Đồ án, Kỷ yếu, Bài báo,...)
class AcademicWork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Tiêu đề công trình, có index để tìm kiếm/sắp xếp
    title = db.Column(db.String(200), nullable=False, index=True)

    is_featured = db.Column(db.Boolean, default=False, nullable=False, server_default='0',index=True)

    # Loại công trình: 'thesis', 'proceeding', 'project', etc. Có index để lọc.
    item_type = db.Column(db.String(20), nullable=False, default='thesis', index=True)

    # Tên tác giả hoặc nhóm tác giả (lưu dạng text cho linh hoạt)
    authors_text = db.Column(db.String(300), nullable=False)

    # Năm hoàn thành hoặc công bố, có index
    year = db.Column(db.Integer, nullable=True, index=True)

    # Phần tóm tắt (Abstract)
    abstract = db.Column(db.Text, nullable=True)

    # Nội dung chi tiết đầy đủ (có thể chứa HTML)
    full_content = db.Column(db.Text, nullable=True)

    # Tên file ảnh minh họa (lưu trong static, ví dụ: static/academic_work_images/)
    image_file = db.Column(db.String(128), nullable=True)

    # Link tham khảo bên ngoài (PDF, Github repo, Website,...)
    external_link = db.Column(db.String(255), nullable=True)

    # Cờ xác định công trình có được hiển thị công khai không (Admin/Dean quản lý)
    is_published = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Ngày công trình được thêm vào hệ thống
    date_added = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # (Nên có) ID của người dùng (Admin/Dean) đã thêm/quản lý công trình này
    # ondelete='SET NULL': Nếu user admin bị xóa, công trình vẫn còn
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    # (Tùy chọn) Relationship ngược lại từ User đến các công trình họ quản lý
    # added_by = db.relationship('User', backref=db.backref('academic_works_managed', lazy='dynamic'))

    # --- Relationship cho chức năng "Like" sẽ thêm ở Giai đoạn 2 ---
    # likes = db.relationship('AcademicWorkLike', backref='academic_work', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        # Hàm __repr__ giúp hiển thị thông tin object khi debug
        return f'<AcademicWork {self.id}: {self.title[:50]}>'


# === THÊM MODEL MỚI CHO LƯỢT LIKE SHOWCASE ===
class AcademicWorkLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # ID của người dùng đã like
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    # ID của công trình được like
    academic_work_id = db.Column(db.Integer, db.ForeignKey('academic_work.id', ondelete='CASCADE'), nullable=False)
    # Thời gian like
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # --- Relationships ---
    # Liên kết đến người dùng
    user = db.relationship('User', backref=db.backref('showcase_likes', lazy='dynamic', cascade='all, delete-orphan'))
    # Liên kết đến công trình
    academic_work = db.relationship('AcademicWork', backref=db.backref('likes', lazy='dynamic', cascade='all, delete-orphan'))

    # --- Ràng buộc duy nhất ---
    # Đảm bảo một người dùng chỉ like một công trình một lần
    __table_args__ = (db.UniqueConstraint('user_id', 'academic_work_id', name='uq_user_academic_work_like'),)

    def __repr__(self):
        return f'<AcademicWorkLike User {self.user_id} liked Item {self.academic_work_id}>'

class PostLike(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        # ID của người dùng đã like
        user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
        # ID của bài đăng (Post) được like
        post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
        # Thời gian like
        timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

        # --- Relationships ---
        # Không cần relationship ngược lại user và post ở đây nếu không dùng trực tiếp thường xuyên
        # Nhưng nên có để tiện truy vấn nếu cần

        # Liên kết đến người dùng (ví dụ: truy cập user_liked = post_like.user)
        user = db.relationship('User', backref=db.backref('post_likes', lazy='dynamic', cascade='all, delete-orphan'))
        # Liên kết đến bài đăng (ví dụ: truy cập liked_post = post_like.post)
        post = db.relationship('Post', backref=db.backref('likes', lazy='dynamic', cascade='all, delete-orphan'))

        # --- Ràng buộc duy nhất ---
        # Đảm bảo một người dùng chỉ like một bài đăng một lần
        __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='uq_user_post_like'),)

        def __repr__(self):
            return f'<PostLike User {self.user_id} liked Post {self.post_id}>'


