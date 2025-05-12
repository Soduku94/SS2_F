# app.py

# Standard library imports
import json
import os
import secrets
import uuid
from datetime import datetime, timezone, date
from functools import wraps

# Third-party imports
import bleach
from dotenv import load_dotenv
from flask import (Flask, render_template, url_for, flash, redirect, request,
                   send_from_directory, abort, jsonify, current_app)
from flask_login import (login_user, current_user, logout_user, login_required)
from flask_wtf.csrf import CSRFProtect
from PIL import Image
from sqlalchemy import asc, desc, or_, func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

# Local application/library specific imports
from extensions import db, migrate, bcrypt, login_manager
from forms import (LoginForm, RegistrationForm, PostForm, UpdateAccountForm,
                   ChangePasswordForm, IdeaSubmissionForm, IdeaReviewForm)
from models import (User, Post, Attachment, StudentIdea, IdeaAttachment, Notification,
                    student_topic_interest, Tag, idea_recipient_lecturers,
                    TopicApplication, AcademicWork, AcademicWorkLike, PostLike)

load_dotenv()

# --- Global Variables / Constants ---
ALLOWED_TAGS = [
    'p', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'br', 'blockquote', 'h1', 'h2', 'h3',
    'a', 'figure', 'figcaption', 'img',
    'pre', 'code', 'div', 'span'
]
ALLOWED_ATTRS = {
    '*': ['class'],
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height']
}
SECRET_KEY_FALLBACK = 'thay-doi-key-nay-ngay-lap-tuc-cho-dev-012345!'

# Pagination Constants
REGULAR_PER_PAGE = 10
FEATURED_PER_PAGE = 4
SEARCH_RESULTS_PER_PAGE = 10
MY_APPLICATIONS_PER_PAGE = 15
PENDING_IDEAS_PER_PAGE = 15  # Matched user's original use
RESPONDED_IDEAS_PER_PAGE = 15  # Matched user's original use
NOTIFICATIONS_PER_PAGE = 15
SHOWCASE_GRID_PER_PAGE = 9
SHOWCASE_CAROUSEL_LIMIT = 5

# --- Flask App Initialization ---
app = Flask(__name__)




# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', SECRET_KEY_FALLBACK)
if app.config['SECRET_KEY'] == SECRET_KEY_FALLBACK:
    app.logger.warning("\n" + "=" * 60)
    app.logger.warning("!!! WARNING: Using fallback SECRET_KEY! !!!")
    app.logger.warning("-> Please create a '.env' file and set SECRET_KEY.")
    app.logger.warning("   Generate with: python -c \"import secrets; print(secrets.token_hex(24))\"")
    if not app.debug:
        app.logger.critical("\n!!! CRITICAL ERROR: DO NOT RUN IN PRODUCTION WITH THIS FALLBACK KEY !!!")
    app.logger.warning("=" * 60 + "\n")

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEFAULT_PICS_FOLDER = os.path.join(app.root_path, 'static', 'profile_pics')
USER_PICS_FOLDER = os.path.join(app.root_path, 'static', 'user_pics')
os.makedirs(DEFAULT_PICS_FOLDER, exist_ok=True)
os.makedirs(USER_PICS_FOLDER, exist_ok=True)
app.config['DEFAULT_PICS_FOLDER'] = DEFAULT_PICS_FOLDER
app.config['USER_PICS_FOLDER'] = USER_PICS_FOLDER

ACADEMIC_WORK_IMAGE_FOLDER = os.path.join(app.root_path, 'static', 'academic_work_images')
os.makedirs(ACADEMIC_WORK_IMAGE_FOLDER, exist_ok=True)
app.config['ACADEMIC_WORK_IMAGE_FOLDER'] = ACADEMIC_WORK_IMAGE_FOLDER

# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Initialize Extensions ---
csrf = CSRFProtect()
csrf.init_app(app)
db.init_app(app)
migrate.init_app(app, db)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- Helper Functions ---
def save_picture(form_picture, old_picture_filename=None):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    user_pics_dir = current_app.config['USER_PICS_FOLDER']
    picture_path = os.path.join(user_pics_dir, picture_fn)

    if old_picture_filename and not old_picture_filename.startswith('default'):
        try:
            old_picture_path = os.path.join(user_pics_dir, old_picture_filename)
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)
        except Exception as e:
            app.logger.error(f"Error deleting old picture {old_picture_path}: {e}")

    output_size = (150, 150)
    try:
        img = Image.open(form_picture)
        img.thumbnail(output_size)
        img.save(picture_path)
        return picture_fn
    except Exception as e:
        app.logger.error(f"Error saving or resizing picture: {e}")
        return None


def _get_int_from_request_arg(arg_name, default=None):
    val_str = request.args.get(arg_name, type=str)
    if val_str and val_str.isdigit():  # Check if it's a digit before converting
        try:
            return int(val_str)
        except ValueError:
            app.logger.warning(f"Invalid integer format for request argument '{arg_name}': {val_str}")
            return default
    return default


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- Context Processors ---
@app.context_processor
def inject_notifications():
    unread_count = 0
    if current_user.is_authenticated:
        try:
            unread_count = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        except Exception as e:
            app.logger.error(f"Error counting unread notifications: {e}")
    return dict(unread_count=unread_count)


# --- Error Handlers ---
@app.errorhandler(403)
def forbidden_access(e):

    return render_template('403.html', title='Truy cập bị chặn'), 403


@app.errorhandler(404)
def page_not_found(e):

    return render_template('404.html', title='Không tìm thấy trang'), 404


# --- Register Blueprints ---
try:
    from admin_routes import admin_bp

    app.register_blueprint(admin_bp)
    app.logger.info("Admin Blueprint registered.")
except ImportError:
    app.logger.warning("Admin Blueprint not found or not registered.")


# --- Routes (Sorted Alphabetically by original function name) ---

@app.route('/account')
@login_required
def account():  # Original name
    cohort = "N/A"
    if current_user.role == 'student' and current_user.student_id and len(current_user.student_id) >= 2:
        try:
            cohort_year_str = current_user.student_id[:2]
            int(cohort_year_str)
            cohort = f"K{cohort_year_str}"
        except ValueError:
            app.logger.warning(f"Could not parse cohort from student_id: {current_user.student_id}")

    return render_template('account_view.html', title='Thông tin Tài khoản', cohort=cohort)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():  # Giữ nguyên tên hàm gốc
    form = UpdateAccountForm()
    if form.validate_on_submit():
        action_taken = False  # Biến cờ để kiểm tra xem có hành động nào được thực hiện không

        # 1. Ưu tiên xử lý xóa ảnh nếu được chọn
        if form.delete_picture.data:
            if current_user.image_file and not current_user.image_file.startswith('default'):
                user_pics_dir = current_app.config.get('USER_PICS_FOLDER',
                                                       os.path.join(current_app.root_path, 'static', 'user_pics'))
                old_picture_path = os.path.join(user_pics_dir, current_user.image_file)
                if os.path.exists(old_picture_path):
                    try:
                        os.remove(old_picture_path)
                        app.logger.info(f"User {current_user.id} deleted profile picture {current_user.image_file}")
                    except Exception as e:
                        app.logger.error(f"Error deleting picture {old_picture_path} for user {current_user.id}: {e}")
                        flash('Error deleting current picture. Please try again.', 'danger')

            current_user.image_file = 'default.jpg'  # Quay về ảnh mặc định chung
            # Logic hiển thị trong template base.html sẽ tự chọn default_male/female nếu cần
            flash('Profile picture has been removed and set to default.', 'success')
            action_taken = True

        # 2. Nếu không xóa, thì mới xử lý tải ảnh mới (nếu có)
        elif form.picture.data:
            # Hàm save_picture của bạn đã có logic xóa ảnh cũ (không phải default) khi lưu ảnh mới
            picture_filename = save_picture(form.picture.data, current_user.image_file)
            if picture_filename:
                current_user.image_file = picture_filename
                # flash('Profile picture updated successfully.', 'success') # Có thể gộp chung thông báo
                action_taken = True
            else:
                flash('Error uploading new picture. Please try again.', 'danger')

        # 3. Cập nhật các thông tin khác
        if (current_user.date_of_birth != form.date_of_birth.data or
                current_user.gender != form.gender.data or
                current_user.phone_number != form.phone_number.data or
                current_user.contact_email != (form.contact_email.data if form.contact_email.data else None) or
                current_user.about_me != form.about_me.data or
                current_user.class_name != form.class_name.data):
            action_taken = True  # Đánh dấu có thay đổi

        current_user.date_of_birth = form.date_of_birth.data
        current_user.gender = form.gender.data
        current_user.phone_number = form.phone_number.data
        current_user.contact_email = form.contact_email.data if form.contact_email.data else None
        current_user.about_me = form.about_me.data
        current_user.class_name = form.class_name.data

        try:
            db.session.commit()
            if action_taken:  # Chỉ flash nếu có thay đổi thực sự
                flash('Your account information has been updated!', 'success')
            else:
                flash('No changes were made to your account information.', 'info')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Commit FAILED in account_edit for user {current_user.id}: {e}")
            flash(f'An error occurred while updating your information: {str(e)}', 'danger')

        return redirect(url_for('account'))

    elif request.method == 'GET':
        form.date_of_birth.data = current_user.date_of_birth
        form.gender.data = current_user.gender
        form.phone_number.data = current_user.phone_number
        form.contact_email.data = current_user.contact_email
        form.about_me.data = current_user.about_me
        form.class_name.data = current_user.class_name
        form.delete_picture.data = False  # Đảm bảo checkbox không được chọn mặc định khi tải trang

    # Giữ nguyên title tiếng Anh bạn đã đặt
    return render_template('account_edit.html', title='Edit Account Information', form=form)

@app.route('/apply-topic/<int:post_id>', methods=['POST'])
@login_required
def apply_to_topic(post_id):  # Original name
    if current_user.role != 'student':

        return jsonify({'status': 'error', 'message': 'Chỉ sinh viên mới có thể đăng ký đề tài.'}), 403

    post = Post.query.get_or_404(post_id)
    if post.post_type != 'topic' or post.status != 'recruiting':

        return jsonify({'status': 'error', 'message': 'Đề tài này không hợp lệ hoặc không còn mở đăng ký.'}), 400

    existing_app = TopicApplication.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing_app:

        return jsonify({'status': 'error', 'message': 'Bạn đã đăng ký đề tài này rồi.'}), 400

    message = request.json.get('message', None) if request.is_json else request.form.get('message', None)
    if message:
        message = message.strip()
        if not message: message = None

    application = TopicApplication(user_id=current_user.id, post_id=post.id, message=message)

    notification_content = f"Sinh viên {current_user.full_name} đã đăng ký đề tài: '{post.title}'"
    new_notification = Notification(
        recipient_id=post.user_id, sender_id=current_user.id, content=notification_content,
        notification_type='topic_application', is_read=False
    )
    try:
        db.session.add(application)
        db.session.add(new_notification)
        db.session.commit()

        return jsonify({'status': 'success', 'applied': True, 'message': 'Đăng ký thành công!'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error applying to topic {post_id} for user {current_user.id}: {e}")

        return jsonify({'status': 'error', 'message': 'Lỗi hệ thống khi đăng ký.'}), 500


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():  # Original name
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.set_password(form.new_password.data)
        try:
            db.session.commit()

            flash('Mật khẩu của bạn đã được cập nhật thành công!', 'success')
            return redirect(url_for('account'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating password for user {current_user.id}: {e}")

            flash(f'Lỗi khi cập nhật mật khẩu: {e}', 'danger')

    return render_template('change_password.html', title='Đổi Mật khẩu', form=form)


@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():  # Original name
    if current_user.role != 'lecturer':

        flash('Bạn không có quyền truy cập chức năng này.', 'danger')
        return redirect(url_for('dashboard'))

    form = PostForm()
    try:
        all_tag_names = [tag.name for tag in Tag.query.order_by(Tag.name).all()]
    except Exception as e:
        app.logger.error(f"Error fetching tags for create_post form: {e}")
        all_tag_names = []

    if form.validate_on_submit():
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        post = Post(title=form.title.data, content=safe_content, post_type=form.post_type.data,
                    is_featured=form.is_featured.data, status=form.status.data, author=current_user)

        attachments_to_add, saved_physical_files, files_saved_count = [], [], 0
        try:
            db.session.add(post)
            db.session.flush()

            tags_input_value = form.tags.data
            tag_names = []
            if tags_input_value:
                try:
                    tag_data_list = json.loads(tags_input_value)
                    tag_names = [item['value'].strip().lower() for item in tag_data_list if
                                 isinstance(item, dict) and item.get('value') and str(item.get('value')).strip()]
                except (json.JSONDecodeError, TypeError, ValueError):
                    tag_names = [name.strip().lower() for name in str(tags_input_value).split(',') if name.strip()]

            if tag_names:
                existing_tags_map = {tag.name: tag for tag in Tag.query.filter(Tag.name.in_(tag_names)).all()}
                for name in tag_names:
                    tag_obj = existing_tags_map.get(name)
                    if not tag_obj:
                        tag_obj = Tag(name=name)
                        db.session.add(tag_obj)
                    post.tags.append(tag_obj)

            if form.attachments.data:
                for file_storage in form.attachments.data:
                    original_filename = secure_filename(file_storage.filename)
                    if original_filename:
                        _, ext = os.path.splitext(original_filename)
                        unique_filename = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        try:
                            file_storage.save(file_path)
                            attachment = Attachment(original_filename=original_filename, saved_filename=unique_filename,
                                                    post_id=post.id)
                            attachments_to_add.append(attachment)
                            saved_physical_files.append(file_path)
                            files_saved_count += 1
                        except Exception as file_e:
                            flash(f'Lỗi khi lưu file {original_filename}: {file_e}.', 'warning')
                            app.logger.error(f"Error saving attachment {original_filename}: {file_e}")

            if attachments_to_add: db.session.add_all(attachments_to_add)
            db.session.commit()

            flash(f'Bài đăng đã được tạo thành công! ({files_saved_count} tệp đính kèm).', 'auth')
            return redirect(url_for('my_posts'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating post: {e}")

            flash(f'Đã xảy ra lỗi khi tạo bài đăng: {e}', 'danger')
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        app.logger.error(f"Error deleting file after create post fail: {remove_err}")
    elif form.errors:
        app.logger.warning(f"Form validation errors (create_post): {form.errors}")

    return render_template('create_post.html', title='Tạo Bài đăng mới', form=form,
                           legend='Tạo Bài đăng / Đề tài', all_tag_names=all_tag_names)


@app.route('/dashboard')
@login_required
def dashboard():  # Original name
    page = _get_int_from_request_arg('page', 1)
    feat_page = _get_int_from_request_arg('feat_page', 1)
    selected_sort = request.args.get('sort', 'date_desc')
    selected_post_type = request.args.get('post_type', '', type=str)
    selected_status = request.args.get('status', '', type=str)
    search_query = request.args.get('q', None, type=str)  # Keep as None if not present

    author_id_filter = _get_int_from_request_arg('author_id')
    tag_id_filter = _get_int_from_request_arg('tag_id')

    featured_pagination = Post.query.filter_by(is_featured=True) \
        .order_by(Post.date_posted.desc()) \
        .paginate(page=feat_page, per_page=FEATURED_PER_PAGE, error_out=False)

    query = Post.query.filter(Post.is_featured == False)  # Start with non-featured posts

    # Join with User if searching by author name or filtering by author_id
    # This logic ensures User is joined only once if multiple conditions require it.
    # It's slightly complex due to multiple potential join triggers.
    # A simpler approach might be to always outerjoin User if any user-related filter/search is active.
    needs_user_join = bool(author_id_filter) or \
                      (search_query and User.full_name.ilike(
                          f"%{search_query}%")._criterion is not None)  # Check if search involves user

    if search_query:
        search_term = f"%{search_query}%"
        # Apply outerjoin to User if not already planned or if search isn't solely on Post fields
        # This specific join logic here might need refinement based on exact search needs on User.
        # For simplicity, if search_query, we often join User.
        query = query.outerjoin(User, Post.user_id == User.id).filter(  # Using outerjoin for safety
            or_(Post.title.ilike(search_term), Post.content.ilike(search_term), User.full_name.ilike(search_term))
        )
        needs_user_join = True  # Mark that User has been joined for this query path

    if author_id_filter is not None:
        if not needs_user_join:  # If search didn't trigger the join
            query = query.join(User, Post.user_id == User.id)  # Now it's a required join
        query = query.filter(User.id == author_id_filter)

    if selected_post_type:
        query = query.filter(Post.post_type == selected_post_type)

    # Status filter logic from original user code (with slight clarification)
    if selected_status:
        if selected_post_type == 'topic':
            if selected_status in ['recruiting', 'working_on', 'closed', 'pending', 'published']:  # Added 'published'
                query = query.filter(Post.post_type == 'topic', Post.status == selected_status)
        elif selected_post_type == 'article':
            if selected_status == 'published':  # Typically only 'published' for articles
                query = query.filter(Post.post_type == 'article', Post.status == selected_status)
        elif not selected_post_type:  # No post_type selected
            if selected_status in ['published', 'closed', 'pending']:  # General statuses
                query = query.filter(Post.status == selected_status)
            elif selected_status == 'recruiting':  # Specific to topic, so add that condition
                query = query.filter(Post.status == selected_status, Post.post_type == 'topic')

    if tag_id_filter is not None:
        # Use .any() for many-to-many relationship filtering
        query = query.filter(Post.tags.any(Tag.id == tag_id_filter))

    if selected_sort == 'date_asc':
        query = query.order_by(Post.date_posted.asc())
    elif selected_sort == 'title_asc':
        query = query.order_by(func.lower(Post.title).asc())
    elif selected_sort == 'title_desc':
        query = query.order_by(func.lower(Post.title).desc())
    else:
        query = query.order_by(Post.date_posted.desc())  # Default

    regular_pagination = query.paginate(page=page, per_page=REGULAR_PER_PAGE, error_out=False)
    posts_on_page = regular_pagination.items
    post_ids_on_page = [p.id for p in posts_on_page if p.id is not None]

    like_counts, user_liked_posts, user_application_status = {}, set(), {}
    if post_ids_on_page:
        try:
            like_counts_query = db.session.query(PostLike.post_id, func.count(PostLike.id)) \
                .filter(PostLike.post_id.in_(post_ids_on_page)).group_by(PostLike.post_id).all()
            like_counts = {pid: count for pid, count in like_counts_query}
        except Exception as e:
            app.logger.error(f"Error fetching like counts for dashboard: {e}")
        if current_user.is_authenticated:
            try:
                user_likes_query = db.session.query(PostLike.post_id).filter(
                    PostLike.user_id == current_user.id, PostLike.post_id.in_(post_ids_on_page)
                ).all()
                user_liked_posts = {pid for (pid,) in user_likes_query}
            except Exception as e:
                app.logger.error(f"Error fetching user likes for dashboard: {e}")
            if current_user.role == 'student':
                try:
                    recruiting_topic_ids = [p.id for p in posts_on_page if
                                            p.post_type == 'topic' and p.status == 'recruiting']
                    if recruiting_topic_ids:
                        user_apps_query = db.session.query(TopicApplication.post_id, TopicApplication.status).filter(
                            TopicApplication.user_id == current_user.id,
                            TopicApplication.post_id.in_(recruiting_topic_ids)
                        ).all()
                        user_application_status = {pid: status for pid, status in user_apps_query}
                except Exception as e:
                    app.logger.error(f"Error fetching user applications for dashboard: {e}")

    lecturers = User.query.filter_by(role='lecturer').order_by(User.full_name).all()
    all_tags = Tag.query.order_by(Tag.name).all()

    return render_template('dashboard.html', title='Bảng điều khiển',
                           featured_pagination=featured_pagination, posts_pagination=regular_pagination,
                           lecturers=lecturers, all_tags=all_tags,
                           selected_sort=selected_sort, selected_author_id=request.args.get('author_id', ''),
                           selected_post_type=selected_post_type, selected_status=selected_status,
                           selected_tag_id=request.args.get('tag_id', ''), search_query=search_query,
                           like_counts=like_counts, user_liked_posts=user_liked_posts,
                           user_application_status=user_application_status)


@app.route('/idea/<int:idea_id>/delete-by-lecturer', methods=['POST'])
@login_required
def delete_idea_by_lecturer(idea_id):  # Original name
    if current_user.role != 'lecturer': abort(403)
    idea = StudentIdea.query.get_or_404(idea_id)
    filenames_to_delete = [att.saved_filename for att in idea.attachments]
    try:
        db.session.delete(idea)
        db.session.commit()
        for filename in filenames_to_delete:
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        app.logger.error(f"Error deleting idea attachment file {file_path} by lecturer: {e}")

        flash('Ý tưởng đã được xóa thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting idea {idea_id} by lecturer: {e}")

        flash(f'Đã xảy ra lỗi khi xóa ý tưởng: {e}', 'danger')
    return redirect(url_for('view_pending_ideas'))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):  # Original name
    post = Post.query.get_or_404(post_id)
    if post.author != current_user: abort(403)
    filenames_to_delete = [att.saved_filename for att in post.attachments]
    try:
        db.session.delete(post)
        db.session.commit()
        for filename in filenames_to_delete:
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        app.logger.error(f"Error deleting post attachment file {file_path}: {e}")

        flash('Bài đăng của bạn đã được xóa!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting post {post_id}: {e}")

        flash(f'Lỗi khi xóa bài đăng: {e}', 'danger')
    return redirect(url_for('my_posts'))


@app.route('/notification/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):  # Original name
    notif = Notification.query.get_or_404(notif_id)
    if notif.recipient_id != current_user.id: abort(403)
    try:
        db.session.delete(notif)
        db.session.commit()

        flash('Đã xóa thông báo.', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting notification {notif_id}: {e}")

        flash(f'Lỗi khi xóa thông báo: {e}', 'danger')
    return redirect(url_for('notifications'))


@app.route('/notifications/delete-all', methods=['POST'])
@login_required
def delete_all_notifications():  # Original name
    try:
        num_deleted = Notification.query.filter_by(recipient_id=current_user.id).delete()
        db.session.commit()
        if num_deleted > 0:

            flash(f'Đã xóa {num_deleted} thông báo.', 'success')
        else:

            flash('Không có thông báo nào để xóa.', 'info')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting all notifications for user {current_user.id}: {e}")

        flash(f'Lỗi khi xóa tất cả thông báo: {e}', 'danger')
    return redirect(url_for('notifications'))


@app.route('/uploads/<path:filename>')  # Path for Post attachments
@login_required
def download_file(filename):  # Kept original name for Post attachments
    attachment = Attachment.query.filter_by(saved_filename=filename).first_or_404()
    # Basic authorization: only post author or admin (can be more granular)
    can_download = False
    if current_user.is_authenticated:
        if current_user.id == attachment.post.user_id or current_user.role == 'admin':
            can_download = True
        # Add other roles/conditions if needed, e.g., students if post is public topic

    if not can_download:
        app.logger.warning(f"Unauthorized attempt to download post attachment {filename} by user {current_user.id}")
        abort(403)

    download_name = attachment.original_filename or filename
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True,
                                   download_name=download_name)
    except FileNotFoundError:
        app.logger.error(f"Post attachment file not found: {filename}")
        abort(404)
    except Exception as e:
        app.logger.error(f"Error downloading post attachment {filename}: {e}")
        abort(500)


@app.route('/idea_uploads/<path:filename>')
@login_required
def download_idea_attachment(filename):  # Original name
    attachment = IdeaAttachment.query.options(joinedload(IdeaAttachment.idea)).get_or_404(
        IdeaAttachment.saved_filename == filename)
    # Authorization: Idea owner, recipient lecturers, or admin
    can_download = False
    if current_user.id == attachment.idea.student_id:
        can_download = True
    elif current_user.role == 'lecturer' and current_user in attachment.idea.recipients:
        can_download = True
    elif current_user.role == 'admin':
        can_download = True

    if not can_download:
        app.logger.warning(f"Unauthorized attempt to download idea attachment {filename} by user {current_user.id}")
        abort(403)

    download_name = attachment.original_filename or filename
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True,
                                   download_name=download_name)
    except FileNotFoundError:
        app.logger.error(f"Idea attachment file not found: {filename}")
        abort(404)
    except Exception as e:
        app.logger.error(f"Error downloading idea attachment {filename}: {e}")
        abort(500)


@app.route('/')
def home():  # Original name
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():  # Original name
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.email) == func.lower(form.email.data)).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')

            flash(f'Đăng nhập thành công cho {user.full_name}!', 'auth')
            return redirect(next_page or url_for('dashboard'))
        else:

            flash('Đăng nhập thất bại. Vui lòng kiểm tra email và mật khẩu.', 'auth')

    return render_template('login.html', title='Đăng nhập', form=form)


@app.route('/logout')
@login_required
def logout():  # Original name
    logout_user()

    flash('Bạn đã đăng xuất.', 'auth')
    return redirect(url_for('login'))


@app.route('/my-applications')
@login_required
def my_applications():  # Original name
    if current_user.role != 'student': abort(403)
    page = _get_int_from_request_arg('page', 1)
    applications_query = TopicApplication.query.filter_by(user_id=current_user.id) \
        .options(joinedload(TopicApplication.topic).joinedload(Post.author)) \
        .order_by(TopicApplication.application_date.desc())
    pagination = applications_query.paginate(page=page, per_page=MY_APPLICATIONS_PER_PAGE, error_out=False)
    return render_template('my_applications.html', title='Registered Topics', applications_pagination=pagination)


@app.route('/my-ideas')
@login_required
def my_ideas():  # Original name
    if current_user.role != 'student': abort(403)
    # Original code fetched all; consider pagination if these lists can grow very large.
    pending_ideas = StudentIdea.query.filter_by(student_id=current_user.id, status='pending') \
        .order_by(StudentIdea.submission_date.desc()).all()
    responded_ideas = StudentIdea.query.filter(StudentIdea.student_id == current_user.id,
                                               StudentIdea.status != 'pending') \
        .order_by(StudentIdea.submission_date.desc()).all()

    return render_template('my_ideas.html', title='My Ideas',
                           pending_ideas=pending_ideas, responded_ideas=responded_ideas)


@app.route('/my-ideas/<int:idea_id>')
@login_required
def view_my_idea(idea_id):  # Original name
    idea = StudentIdea.query.get_or_404(idea_id)
    if idea.student_id != current_user.id: abort(403)
    return render_template('view_my_idea.html', title=idea.title, idea=idea)


@app.route('/my-ideas/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_my_idea(idea_id):  # Original name
    idea = StudentIdea.query.get_or_404(idea_id)
    if idea.student_id != current_user.id: abort(403)
    filenames_to_delete = [att.saved_filename for att in idea.attachments]
    try:
        db.session.delete(idea)
        db.session.commit()
        for filename in filenames_to_delete:
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        app.logger.error(f"Error deleting idea attachment file {file_path}: {e}")

        flash('Ý tưởng của bạn đã được xóa!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting my idea {idea_id}: {e}")

        flash(f'Lỗi khi xóa ý tưởng: {e}', 'danger')
    return redirect(url_for('my_ideas'))


@app.route('/my-posts')
@login_required
def my_posts():  # Original name
    if current_user.role != 'lecturer':

        flash('Chức năng này dành cho Giảng viên.', 'info')
        return redirect(url_for('dashboard'))
    page = _get_int_from_request_arg('page', 1)
    posts_query = Post.query.filter_by(author=current_user).order_by(Post.date_posted.desc())
    pagination = posts_query.paginate(page=page, per_page=REGULAR_PER_PAGE, error_out=False)
    posts_on_page = pagination.items
    post_ids_on_page = [p.id for p in posts_on_page if p.id is not None]
    like_counts, user_liked_posts = {}, set()
    if post_ids_on_page:
        try:
            like_counts_query = db.session.query(PostLike.post_id, func.count(PostLike.id)) \
                .filter(PostLike.post_id.in_(post_ids_on_page)).group_by(PostLike.post_id).all()
            like_counts = {pid: count for pid, count in like_counts_query}
        except Exception as e:
            app.logger.error(f"Error fetching like counts for my_posts: {e}")
        try:
            user_likes_query = db.session.query(PostLike.post_id).filter(
                PostLike.user_id == current_user.id, PostLike.post_id.in_(post_ids_on_page)
            ).all()
            user_liked_posts = {pid for (pid,) in user_likes_query}
        except Exception as e:
            app.logger.error(f"Error fetching user likes for my_posts: {e}")

    return render_template('my_posts.html', title='Bài đăng của tôi',
                           posts_pagination=pagination, like_counts=like_counts,
                           user_liked_posts=user_liked_posts)


@app.route('/notifications')
@login_required
def notifications():  # Original name
    unread_notifications = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).all()
    if unread_notifications:
        for notif in unread_notifications: notif.is_read = True
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error marking notifications as read for user {current_user.id}: {e}")

            flash("Có lỗi xảy ra khi cập nhật trạng thái thông báo.", "warning")
    page = _get_int_from_request_arg('page', 1)
    pagination = Notification.query.filter_by(recipient_id=current_user.id) \
        .order_by(Notification.timestamp.desc()) \
        .paginate(page=page, per_page=NOTIFICATIONS_PER_PAGE, error_out=False)

    return render_template('notifications.html', title='Your notifications', notifications_pagination=pagination)


@app.route('/pending-ideas')
@login_required
def view_pending_ideas():  # Original name
    if current_user.role not in ['lecturer', 'admin']: abort(403)
    page = _get_int_from_request_arg('page', 1)
    query = StudentIdea.query.filter(
        StudentIdea.status == 'pending',
        ~(StudentIdea.recipients.any() & ~StudentIdea.recipients.any(User.id == current_user.id))
    )
    pagination = query.order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=PENDING_IDEAS_PER_PAGE, error_out=False)

    return render_template('view_ideas_list.html', title='Ý tưởng Chờ Duyệt',
                           ideas_pagination=pagination, list_title='Danh sách Ý tưởng Chờ Duyệt',
                           active_tab='pending')


@app.route('/post/<int:post_id>')
@login_required
def view_post(post_id):  # Original name
    post = Post.query.get_or_404(post_id)
    post_like_count, user_has_liked_post = 0, False
    try:
        post_like_count = db.session.query(func.count(PostLike.id)).filter(PostLike.post_id == post.id).scalar() or 0
        if current_user.is_authenticated:
            user_has_liked_post = PostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
    except Exception as e:
        app.logger.error(f"Error fetching like info for post {post_id}: {e}")

    application = None
    if post.post_type == 'topic' and current_user.is_authenticated and current_user.role == 'student':
        try:
            application = TopicApplication.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        except Exception as e:
            app.logger.error(f"Error fetching application info for post {post_id}, user {current_user.id}: {e}")

    return render_template('post_detail.html', title=post.title, post=post, application=application,
                           like_count=post_like_count, user_has_liked=user_has_liked_post)


@app.route('/post/<int:post_id>/applications')
@login_required
def view_topic_applications(post_id):  # Original name
    topic = Post.query.options(joinedload(Post.author)).get_or_404(post_id)
    # Allow admin to view applications too
    if topic.author != current_user and current_user.role != 'admin':
        abort(403)
    if topic.post_type != 'topic':

        flash('Chức năng này chỉ áp dụng cho Đề tài Nghiên cứu.', 'warning')
        return redirect(url_for('view_post', post_id=topic.id))
    try:
        all_apps = TopicApplication.query.filter_by(post_id=topic.id) \
            .options(joinedload(TopicApplication.student)) \
            .order_by(TopicApplication.application_date.desc()).all()

        pending_apps = [app for app in all_apps if app.status == 'pending']
        approved_apps = [app for app in all_apps if app.status == 'accepted']
        rejected_apps = [app for app in all_apps if app.status == 'rejected']
    except Exception as e:
        # app.logger.error(f"Error querying applications for post {topic.id}: {e}")
        pending_apps, approved_apps, rejected_apps = [], [], []

        flash("Lỗi khi tải danh sách đơn đăng ký.", "danger")
    # Using topic.title for the page title
    return render_template('topic_applications.html', topic=topic,
                           title=f"Applications for '{topic.title}'",  # Dynamic title
                           pending_apps=pending_apps, approved_apps=approved_apps, rejected_apps=rejected_apps)


@app.route('/post/<int:post_id>/toggle_like', methods=['POST'])
@login_required
def toggle_post_like(post_id):  # Original name
    post = Post.query.get_or_404(post_id)
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    user_liked_now = False
    try:
        if like:
            db.session.delete(like)
        else:
            new_like = PostLike(user_id=current_user.id, post_id=post.id)
            db.session.add(new_like)
            user_liked_now = True
        db.session.commit()
        like_count = PostLike.query.filter_by(post_id=post.id).count()
        return jsonify({'status': 'success', 'liked': user_liked_now, 'like_count': like_count})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error toggling like for post {post_id}, user {current_user.id}: {e}")

        return jsonify({'status': 'error', 'message': 'Đã xảy ra lỗi khi xử lý lượt thích.'}), 500


@app.route('/post/<int:post_id>/update', methods=['GET', 'POST'])
@login_required
def update_post(post_id):  # Original name
    post = Post.query.options(joinedload(Post.attachments)).get_or_404(post_id)
    if post.author != current_user: abort(403)
    form = PostForm()
    try:
        all_tag_names = [tag.name for tag in Tag.query.order_by(Tag.name).all()]
    except Exception as e:
        app.logger.error(f"Error fetching tags for post update form: {e}")
        all_tag_names = []

    if form.validate_on_submit():
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        post.title = form.title.data
        post.content = safe_content
        post.post_type = form.post_type.data
        post.status = form.status.data
        post.is_featured = form.is_featured.data

        attachments_to_add, saved_physical_files, old_filenames_to_delete = [], [], []
        files_were_uploaded = bool(form.attachments.data and any(f.filename for f in form.attachments.data))

        try:
            tags_input_value = form.tags.data
            updated_post_tags = []
            if tags_input_value:
                tag_names = []
                try:
                    tag_data_list = json.loads(tags_input_value)
                    tag_names = [item['value'].strip().lower() for item in tag_data_list if
                                 isinstance(item, dict) and item.get('value') and str(item.get('value')).strip()]
                except (json.JSONDecodeError, TypeError, ValueError):
                    tag_names = [name.strip().lower() for name in str(tags_input_value).split(',') if name.strip()]

                if tag_names:
                    existing_tags_map = {tag.name: tag for tag in Tag.query.filter(Tag.name.in_(tag_names)).all()}
                    for name in tag_names:
                        tag_obj = existing_tags_map.get(name)
                        if not tag_obj:
                            tag_obj = Tag(name=name)
                            db.session.add(tag_obj)
                        updated_post_tags.append(tag_obj)
            post.tags = updated_post_tags

            if files_were_uploaded:
                old_filenames_to_delete = [att.saved_filename for att in post.attachments]
                for att_to_delete in list(post.attachments): db.session.delete(att_to_delete)
                post.attachments.clear()
                db.session.flush()

                for file_storage in form.attachments.data:
                    original_filename = secure_filename(file_storage.filename)
                    if original_filename:
                        _, ext = os.path.splitext(original_filename)
                        unique_filename = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        try:
                            file_storage.save(file_path)
                            attachment = Attachment(original_filename=original_filename, saved_filename=unique_filename,
                                                    post_id=post.id)
                            attachments_to_add.append(attachment)
                            saved_physical_files.append(file_path)
                        except Exception as file_e:

                            flash(f'Lỗi khi lưu file mới {original_filename}.', 'warning')
                            app.logger.error(f"Error saving new attachment {original_filename}: {file_e}")
                post.attachments = attachments_to_add

            db.session.commit()
            files_saved_count = db.session.query(Attachment).filter_by(post_id=post.id).count()

            flash(f'Bài đăng đã được cập nhật! ({files_saved_count} tệp đính kèm).', 'success')

            if files_were_uploaded and old_filenames_to_delete:
                for filename in old_filenames_to_delete:
                    if filename:
                        old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        if os.path.exists(old_file_path):
                            try:
                                os.remove(old_file_path)
                            except Exception as e:
                                app.logger.error(f"Update Error deleting old file {old_file_path}: {e}")
            return redirect(url_for('view_post', post_id=post.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Commit FAILED in update_post for post {post_id}: {e}")

            flash(f'Lỗi khi cập nhật bài đăng: {e}', 'danger')
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        app.logger.error(f"Error deleting NEW file after update post fail: {remove_err}")

    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
        form.post_type.data = post.post_type
        form.status.data = post.status
        form.is_featured.data = post.is_featured
        form.tags.data = ', '.join([tag.name for tag in post.tags]) if post.tags else ''
    elif form.errors:
        app.logger.warning(f"Form validation errors (update_post): {form.errors}")

    current_tags_string = ', '.join([tag.name for tag in post.tags]) if post.tags else ''

    return render_template('create_post.html', title='Cập nhật Bài đăng', form=form,
                           legend=f'Cập nhật: {post.title}', post=post,
                           all_tag_names=all_tag_names, current_tags_string=current_tags_string)


@app.route('/register', methods=['GET', 'POST'])
def register():  # Original name
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            full_name=form.full_name.data, student_id=form.student_id.data, email=form.email.data,
            class_name=form.class_name.data, date_of_birth=form.date_of_birth.data,
            gender=form.gender.data, phone_number=form.phone_number.data,
            password_hash=hashed_password, role='student'
        )
        try:
            db.session.add(user)
            db.session.commit()

            flash(f'Tài khoản sinh viên cho {form.full_name.data} đã được tạo! Bạn có thể đăng nhập.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating account for {form.email.data}: {e}")

            flash(f'Lỗi khi tạo tài khoản: {e}', 'danger')

    return render_template('register/register.html', title='Đăng ký Sinh viên', form=form)


@app.route('/responded-ideas')
@login_required
def view_responded_ideas():  # Original name
    if current_user.role not in ['lecturer', 'admin']: abort(403)
    page = _get_int_from_request_arg('page', 1)
    query = StudentIdea.query.filter(
        StudentIdea.status != 'pending',
        ~(StudentIdea.recipients.any() & ~StudentIdea.recipients.any(User.id == current_user.id))
    )
    pagination = query.order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=RESPONDED_IDEAS_PER_PAGE, error_out=False)

    return render_template('view_ideas_list.html', title='Ý tưởng Đã Phản hồi',
                           ideas_pagination=pagination, list_title='Danh sách Ý tưởng Đã Phản hồi',
                           active_tab='responded')


@app.route('/idea/<int:idea_id>/review', methods=['GET', 'POST'])
@login_required
def review_idea(idea_id):  # Original name
    if current_user.role != 'lecturer': abort(403)
    idea = StudentIdea.query.get_or_404(idea_id)
    form = IdeaReviewForm()

    if form.validate_on_submit():
        original_status = idea.status
        idea.status = form.status.data
        idea.feedback = form.feedback.data.strip() if form.feedback.data else None

        notification_to_add = None
        if idea.status != original_status or idea.feedback:

            status_text_map = {'approved': 'được chấp thuận', 'rejected': 'bị từ chối',
                               'reviewed': 'đã được xem xét', 'pending': 'quay lại chờ duyệt'}
            status_text = status_text_map.get(idea.status, f'cập nhật thành {idea.status}')
            feedback_text = " và có phản hồi mới" if idea.feedback else ""
            notif_content = f"Ý tưởng \"{idea.title[:30]}...\" của bạn đã {status_text}{feedback_text}."
            notification_to_add = Notification(
                content=notif_content, recipient_id=idea.student_id,
                related_idea_id=idea.id, sender_id=current_user.id
            )
        try:
            if notification_to_add: db.session.add(notification_to_add)
            db.session.commit()

            flash(f'Đã cập nhật trạng thái và phản hồi cho ý tưởng "{idea.title}".', 'success')

            redirect_target = 'view_responded_ideas' if idea.status != 'pending' else 'view_pending_ideas'
            if redirect_target not in app.view_functions: redirect_target = 'dashboard'
            return redirect(url_for(redirect_target))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating idea review for idea {idea_id}: {e}")

            flash(f'Lỗi khi cập nhật ý tưởng: {e}', 'danger')

    elif request.method == 'GET':
        form.status.data = idea.status
        form.feedback.data = idea.feedback

    return render_template('review_idea.html', title=f"Review: {idea.title}", idea=idea, form=form)


@app.route('/search')
@login_required
def search_results():  # Original name
    search_query = request.args.get('q', '', type=str).strip()
    page = _get_int_from_request_arg('page', 1)
    selected_sort = request.args.get('sort', 'date_desc')
    selected_post_type = request.args.get('post_type', '', type=str)
    selected_status = request.args.get('status', '', type=str)

    author_id_filter = _get_int_from_request_arg('author_id')

    query = Post.query
    joined_user_for_search = False

    if search_query:
        search_term = f"%{search_query}%"
        query = query.outerjoin(User, Post.user_id == User.id)  # Join for author name search
        query = query.filter(
            or_(Post.title.ilike(search_term), Post.content.ilike(search_term), User.full_name.ilike(search_term))
        )
        joined_user_for_search = True  # User table has been joined

    if author_id_filter is not None:
        if not joined_user_for_search:  # If search didn't already join User
            query = query.join(User, Post.user_id == User.id)
        query = query.filter(User.id == author_id_filter)

    if selected_post_type: query = query.filter(Post.post_type == selected_post_type)

    if selected_status:
        if selected_post_type == 'topic' and selected_status in ['recruiting', 'working_on', 'closed', 'pending',
                                                                 'published']:
            query = query.filter(Post.status == selected_status)
        elif selected_post_type == 'article' and selected_status == 'published':
            query = query.filter(Post.status == selected_status)
        elif not selected_post_type and selected_status in ['published', 'pending', 'closed']:
            query = query.filter(Post.status == selected_status)

    if selected_sort == 'date_asc':
        query = query.order_by(Post.date_posted.asc())
    elif selected_sort == 'title_asc':
        query = query.order_by(asc(func.lower(Post.title)))
    elif selected_sort == 'title_desc':
        query = query.order_by(desc(func.lower(Post.title)))
    else:
        query = query.order_by(Post.date_posted.desc())

    search_pagination = query.paginate(page=page, per_page=SEARCH_RESULTS_PER_PAGE, error_out=False)
    lecturers = User.query.filter_by(role='lecturer').order_by(User.full_name).all()

    title_str = f"Kết quả tìm kiếm cho '{search_query}'" if search_query else "Tìm kiếm"
    return render_template('search_results.html', title=title_str, q=search_query,
                           posts_pagination=search_pagination, lecturers=lecturers,
                           selected_sort=selected_sort, selected_author_id=request.args.get('author_id', ''),
                           selected_post_type=selected_post_type, selected_status=selected_status)


@app.route('/showcase')
def showcase():  # Original name
    page = _get_int_from_request_arg('page', 1)
    filter_type = request.args.get('item_type', None, type=str)
    filter_year = _get_int_from_request_arg('year')

    try:
        carousel_items = AcademicWork.query.filter_by(is_published=True, is_featured=True) \
            .order_by(AcademicWork.date_added.desc()).limit(SHOWCASE_CAROUSEL_LIMIT).all()
    except Exception as e:
        app.logger.error(f"Error querying carousel items for showcase: {e}")
        carousel_items = []

    try:
        query = AcademicWork.query.filter_by(is_published=True)
        if filter_type: query = query.filter(AcademicWork.item_type == filter_type)
        if filter_year is not None: query = query.filter(AcademicWork.year == filter_year)
        query = query.order_by(AcademicWork.year.desc().nullslast(), AcademicWork.date_added.desc())
        items_pagination = query.paginate(page=page, per_page=SHOWCASE_GRID_PER_PAGE, error_out=False)
    except Exception as e:
        app.logger.error(f"Error querying grid items for showcase: {e}")
        items_pagination = None

        flash("Lỗi khi tải danh sách công trình.", "danger")

    try:
        distinct_types = [r[0] for r in db.session.query(AcademicWork.item_type).filter(
            AcademicWork.is_published == True).distinct().order_by(AcademicWork.item_type).all()]
        distinct_years = [r[0] for r in db.session.query(AcademicWork.year).filter(AcademicWork.is_published == True,
                                                                                   AcademicWork.year.isnot(
                                                                                       None)).distinct().order_by(
            AcademicWork.year.desc()).all()]
    except Exception as e:
        app.logger.error(f"Error fetching distinct filters for showcase: {e}")
        distinct_types, distinct_years = [], []

    return render_template('showcase_list.html', title="Featured Projects",
                           carousel_items=carousel_items, items_pagination=items_pagination,
                           distinct_types=distinct_types, distinct_years=distinct_years,
                           filter_type=filter_type, filter_year=request.args.get('year', ''))


@app.route('/showcase/<int:item_id>')
def showcase_detail(item_id):  # Original name
    item = AcademicWork.query.filter_by(id=item_id, is_published=True).first_or_404()
    like_count, user_has_liked = 0, False
    try:
        like_count = db.session.query(func.count(AcademicWorkLike.id)).filter(
            AcademicWorkLike.academic_work_id == item.id).scalar() or 0
        if current_user.is_authenticated:
            user_has_liked = AcademicWorkLike.query.filter_by(user_id=current_user.id,
                                                              academic_work_id=item.id).first() is not None
    except Exception as e:
        app.logger.error(f"Error fetching like info for showcase item {item_id}: {e}")
    return render_template('showcase_detail.html', title=item.title, item=item,
                           like_count=like_count, user_has_liked=user_has_liked)


@app.route('/showcase/<int:item_id>/toggle_like', methods=['POST'])
@login_required
def toggle_showcase_like(item_id):  # Original name
    item = AcademicWork.query.get_or_404(item_id)
    if not item.is_published:
        return jsonify({'status': 'error', 'message': 'Item not published.'}), 403

    like = AcademicWorkLike.query.filter_by(user_id=current_user.id, academic_work_id=item.id).first()
    user_liked_now = False
    try:
        if like:
            db.session.delete(like)
        else:
            new_like = AcademicWorkLike(user_id=current_user.id, academic_work_id=item.id)
            db.session.add(new_like)
            user_liked_now = True
        db.session.commit()
        like_count = AcademicWorkLike.query.filter_by(academic_work_id=item.id).count()
        return jsonify({'status': 'success', 'liked': user_liked_now, 'like_count': like_count})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in toggle_showcase_like for item {item_id}, user {current_user.id}: {e}")

        return jsonify({'status': 'error', 'message': 'Đã xảy ra lỗi, vui lòng thử lại.'}), 500


@app.route('/idea/submit', methods=['GET', 'POST'])
@login_required
def submit_idea():  # Original name
    if current_user.role != 'student':

        flash('Chỉ sinh viên mới có thể gửi ý tưởng.', 'warning')
        return redirect(url_for('dashboard'))
    form = IdeaSubmissionForm()
    try:
        form.recipients.choices = [(l.id, l.full_name) for l in
                                   User.query.filter_by(role='lecturer').order_by(User.full_name).all()]
    except Exception as e:
        app.logger.error(f"Error loading lecturer choices for idea form: {e}")

        flash('Lỗi tải danh sách giảng viên.', 'danger')
        form.recipients.choices = []

    if form.validate_on_submit():
        safe_description = bleach.clean(form.description.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        idea = StudentIdea(title=form.title.data, description=safe_description, student_id=current_user.id)

        attachments_to_add, saved_physical_files, files_saved_count = [], [], 0
        try:
            db.session.add(idea)
            selected_recipient_ids = form.recipients.data
            if selected_recipient_ids:
                idea.recipients = User.query.filter(User.id.in_(selected_recipient_ids), User.role == 'lecturer').all()
            else:
                idea.recipients = []
            db.session.flush()

            if form.attachments.data:
                for file_storage in form.attachments.data:
                    original_filename = secure_filename(file_storage.filename)
                    if original_filename:
                        _, ext = os.path.splitext(original_filename)
                        unique_filename = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        try:
                            file_storage.save(file_path)
                            attachment = IdeaAttachment(original_filename=original_filename,
                                                        saved_filename=unique_filename, idea_id=idea.id)
                            attachments_to_add.append(attachment)
                            saved_physical_files.append(file_path)
                            files_saved_count += 1
                        except Exception as file_e:

                            flash(f'Lỗi khi lưu file {original_filename}.', 'warning')
                            app.logger.error(f"Error saving idea attachment {original_filename}: {file_e}")

            if attachments_to_add: db.session.add_all(attachments_to_add)

            notifications_to_add = []
            if idea.recipients:  # Check if list is not empty
                for lecturer in idea.recipients:

                    notification_content = f"Sinh viên {current_user.full_name} đã gửi một ý tưởng mới: '{idea.title}'"
                    new_notification = Notification(
                        recipient_id=lecturer.id, sender_id=current_user.id, content=notification_content,
                        notification_type='new_idea', related_idea_id=idea.id, is_read=False
                    )
                    notifications_to_add.append(new_notification)
            if notifications_to_add: db.session.add_all(notifications_to_add)

            db.session.commit()

            flash(f'Ý tưởng của bạn đã được gửi thành công! ({files_saved_count} tệp đính kèm).', 'success')
            return redirect(url_for('my_ideas'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error submitting idea: {e}")

            flash(f'Lỗi khi gửi ý tưởng: {e}', 'danger')
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        app.logger.error(f"Error deleting file after submit idea fail: {remove_err}")
    elif form.errors:
        app.logger.warning(f"Form validation errors (submit_idea): {form.errors}")

    return render_template('submit_idea.html', title='Gửi Ý tưởng Mới', form=form)

@app.route('/application/<int:application_id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(application_id): # Tên hàm gốc được giữ lại
    application = TopicApplication.query.options(joinedload(TopicApplication.topic)).get_or_404(application_id)
    if application.user_id != current_user.id:
        abort(403)
    if application.status != 'pending':

        return jsonify({'status': 'error', 'message': 'Đơn đã được xử lý.'}), 400

    post_author_id = application.topic.user_id if application.topic else None
    post_title = application.topic.title if application.topic else "Không rõ" #

    try:
        db.session.delete(application)
        if post_author_id:

            notification_content = f"Sinh viên {current_user.full_name} đã hủy đăng ký đề tài: '{post_title[:30]}...'"
            new_notification = Notification(
                recipient_id=post_author_id, sender_id=current_user.id, content=notification_content,
                notification_type='application_withdrawn', is_read=False
            )
            db.session.add(new_notification)
        db.session.commit()

        return jsonify({'status': 'success', 'applied': False, 'message': 'Đã hủy đăng ký đề tài!'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error withdrawing application {application_id}: {e}")

        return jsonify({'status': 'error', 'message': f'Lỗi khi hủy đăng ký: {e}'}), 500
# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)