# app.py

# import các thứ
import json
import os
import secrets
import uuid
import bleach

from PIL import Image
from functools import wraps
from datetime import datetime, timezone, date  # Thêm date nếu models dùng
from flask import (Flask, render_template, url_for, flash, redirect, request,
                   send_from_directory, abort, jsonify, current_app)
from sqlalchemy import asc, desc, or_, MetaData
from sqlalchemy.testing.plugin.plugin_base import post
from werkzeug.utils import secure_filename

from models import StudentIdea, Notification, TopicApplication

# Import Extensions (Một lần)
from extensions import db, migrate, bcrypt, login_manager

# Import Models (Một lần)
from models import (User, Post, Attachment, StudentIdea, IdeaAttachment, Notification,
                    student_topic_interest, Tag, idea_recipient_lecturers)  # Đảm bảo đủ

# Import Forms (Một lần)
from forms import (LoginForm, RegistrationForm, PostForm, UpdateAccountForm,
                   ChangePasswordForm, IdeaSubmissionForm, IdeaReviewForm)

# Import Flask-Login components (Một lần)
from flask_login import login_user, current_user, logout_user, login_required

# --- Khởi tạo App và Extensions ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_change_this'  # <<< NHỚ THAY KEY! >>>
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# (Tùy chọn) Giới hạn kích thước file upload
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Khởi tạo Extensions ---
# Naming convention được định nghĩa và truyền vào khi tạo db trong extensions.py
# Nếu bạn chưa làm vậy, hãy làm theo hướng dẫn cũ hoặc bỏ metadata=metadata ở dưới
# convention = { ... }
# metadata = MetaData(naming_convention=convention)
# db = SQLAlchemy(metadata=metadata) -> nên đặt trong extensions.py
# db = SQLAlchemy() # Nếu không dùng Naming Convention ngay
# <<< THÊM PHẦN NÀY CHO THƯ MỤC ẢNH PROFILE >>>


# --- CẬP NHẬT/THÊM ĐƯỜNG DẪN ẢNH ---
# Thư mục cho ảnh mặc định (đã có)
DEFAULT_PICS_FOLDER = os.path.join(app.root_path, 'static', 'profile_pics')
os.makedirs(DEFAULT_PICS_FOLDER, exist_ok=True)

# Thư mục MỚI cho ảnh user upload
USER_PICS_FOLDER = os.path.join(app.root_path, 'static', 'user_pics')
os.makedirs(USER_PICS_FOLDER, exist_ok=True)

# Lưu vào config nếu muốn (tùy chọn, nhưng tiện lợi)
app.config['DEFAULT_PICS_FOLDER'] = DEFAULT_PICS_FOLDER
app.config['USER_PICS_FOLDER'] = USER_PICS_FOLDER

UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)
migrate.init_app(app, db)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Đăng ký Blueprint
try:
    from admin_routes import admin_bp

    app.register_blueprint(admin_bp)
    print("Admin Blueprint registered.")
except ImportError:
    print("Admin Blueprint not found or not registered.")

# cho phép các tag cho RTE
ALLOWED_TAGS = [
    'p', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'br', 'blockquote', 'h1', 'h2', 'h3',
    'a', 'figure', 'figcaption', 'img',  # Thêm thẻ cho ảnh nếu Trix cho phép chèn ảnh
    'pre', 'code', 'div', 'span'  # Thêm thẻ cho code block, định dạng cơ bản
]
ALLOWED_ATTRS = {
    '*': ['class'],  # Cho phép class cho nhiều thẻ (Trix hay dùng)
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height']  # Cho phép thuộc tính ảnh
}


# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', title='Không tìm thấy trang'), 404


@app.errorhandler(403)
def forbidden_access(e):
    # Bạn cần tạo file templates/403.html tương tự 404.html
    return render_template('403.html', title='Truy cập bị chặn'), 403


# --- Routes ---


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Đăng nhập thành công cho {user.full_name}!', 'auth')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Đăng nhập thất bại. Vui lòng kiểm tra email và mật khẩu.', 'auth')
            print("DEBUG: Flashed 'Login Failed' message.")
    return render_template('login.html', title='Đăng nhập', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Chuyển hướng nếu đã đăng nhập
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()  # Dùng form đã cập nhật
    if form.validate_on_submit():
        # Hash mật khẩu
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        # Tạo đối tượng User mới với ĐẦY ĐỦ thông tin từ form
        user = User(
            full_name=form.full_name.data,
            student_id=form.student_id.data,
            email=form.email.data,  # Email đăng nhập
            class_name=form.class_name.data,  # Lớp học
            date_of_birth=form.date_of_birth.data,  # Ngày sinh
            gender=form.gender.data,  # Giới tính
            phone_number=form.phone_number.data,  # Số điện thoại
            password_hash=hashed_password,
            role='student'  # <<< Luôn đặt role là 'student' cho form này
            # Các trường khác như contact_email, about_me sẽ là NULL ban đầu
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Tài khoản sinh viên cho {form.full_name.data} đã được tạo! Bạn có thể đăng nhập.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi tạo tài khoản: {e}', 'danger')

    # Render template đăng ký (sẽ cập nhật ở bước sau)
    return render_template('register.html', title='Đăng ký Sinh viên', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất.', 'auth')
    return redirect(url_for('login'))


# --- CODE HOÀN CHỈNH CHO ROUTE DASHBOARD (VỚI LỌC/SẮP XẾP) ---


@app.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    feat_page = request.args.get('feat_page', 1, type=int)
    selected_sort = request.args.get('sort', 'date_desc')
    selected_author_id = request.args.get('author_id', '', type=str)
    selected_post_type = request.args.get('post_type', '', type=str)
    selected_status = request.args.get('status', '', type=str)
    search_query = request.args.get('q', None, type=str)  # Lấy q từ dashboard filter/search

    REGULAR_PER_PAGE = 10
    FEATURED_PER_PAGE = 4

    featured_pagination = Post.query.filter_by(is_featured=True) \
        .order_by(Post.date_posted.desc()) \
        .paginate(page=feat_page, per_page=FEATURED_PER_PAGE, error_out=False)

    query = Post.query.filter_by(is_featured=False)
    needs_join = False
    # Áp dụng Filter/Sort/Search (giống logic trong route search_results)
    if search_query:  # Nếu có tìm kiếm từ chính dashboard (ví dụ)
        search_term = f"%{search_query}%"
        query = query.join(User, Post.user_id == User.id).filter(
            or_(Post.title.ilike(search_term), Post.content.ilike(search_term), User.full_name.ilike(search_term)))
    else:  # Chỉ lọc/sort
        needs_join = bool(selected_author_id)
        if needs_join: query = query.join(User, Post.user_id == User.id)

    if selected_author_id: query = query.filter(User.id == selected_author_id)
    if selected_post_type: query = query.filter(Post.post_type == selected_post_type)
    if selected_post_type == 'topic' and selected_status: query = query.filter(Post.status == selected_status)

    if selected_sort == 'date_asc':
        query = query.order_by(Post.date_posted.asc())
    elif selected_sort == 'title_asc':
        query = query.order_by(asc(db.func.lower(Post.title)))
    elif selected_sort == 'title_desc':
        query = query.order_by(desc(db.func.lower(Post.title)))
    else:
        query = query.order_by(Post.date_posted.desc())

    regular_pagination = query.paginate(page=page, per_page=REGULAR_PER_PAGE, error_out=False)
    lecturers = User.query.filter_by(role='lecturer').order_by(User.full_name).all()

    return render_template('dashboard.html', title='Bảng điều khiển',
                           featured_pagination=featured_pagination, posts_pagination=regular_pagination,
                           lecturers=lecturers, selected_sort=selected_sort,
                           selected_author_id=selected_author_id, selected_post_type=selected_post_type,
                           selected_status=selected_status, search_query=search_query)


# Trong app.py

# Đảm bảo đã import Tag ở đầu file app.py
# from models import Tag # <<<< KIỂM TRA IMPORT NÀY

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.role != 'lecturer':
        flash('Bạn không có quyền truy cập chức năng này.', 'danger')
        return redirect(url_for('dashboard'))

    form = PostForm()

    # --- Lấy danh sách tên các tag đã có (cho Tagify whitelist) ---
    try:
        all_tags = Tag.query.order_by(Tag.name).all()
        all_tag_names = [tag.name for tag in all_tags]
    except Exception as e:
        print(f"Lỗi khi lấy danh sách tags cho form: {e}")
        all_tag_names = []
    # --------------------------------------------------------------

    if form.validate_on_submit():
        # Làm sạch nội dung
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

        # Tạo đối tượng Post
        post = Post(title=form.title.data, content=safe_content, post_type=form.post_type.data,
                    is_featured=form.is_featured.data, status=form.status.data, author=current_user)

        # Khởi tạo các biến
        attachments_to_add = []
        saved_physical_files = []
        files_saved_count = 0
        post_id_to_assign = None

        try:
            # Thêm post vào session
            db.session.add(post)
            # Flush để lấy ID và các thay đổi có hiệu lực trước các bước sau
            db.session.flush()
            post_id_to_assign = post.id

            # >>>>>>>>>>>>>>>>>> START: KHỐI XỬ LÝ TAGS ĐÃ SỬA (XỬ LÝ JSON) >>>>>>>>>>>>>>>>>>
            tags_input_value = form.tags.data  # Giá trị từ input (có thể là JSON string)
            post_tags_objects = []  # List để giữ các đối tượng Tag cuối cùng
            tag_names = []  # List để giữ tên tag đã parse

            if tags_input_value:  # Chỉ xử lý nếu có dữ liệu
                try:
                    # THỬ parse dữ liệu đầu vào như là một chuỗi JSON
                    tag_data_list = json.loads(tags_input_value)
                    # Trích xuất tên tag từ key 'value' trong mỗi dictionary
                    # Thêm kiểm tra để đảm bảo item là dict và có key 'value' và value không rỗng
                    tag_names = [
                        item['value'].strip().lower()
                        for item in tag_data_list
                        if isinstance(item, dict) and item.get('value') and str(item.get('value')).strip()
                    ]
                    print(f"DEBUG (create_post): Parsed tags from JSON: {tag_names}")  # Debug

                except (json.JSONDecodeError, TypeError, ValueError):
                    # NẾU KHÔNG PHẢI JSON hoặc lỗi parse -> Coi như là chuỗi cách nhau bởi dấu phẩy
                    print(
                        f"DEBUG (create_post): Failed to parse as JSON, treating as comma-separated: '{tags_input_value}'")  # Debug
                    tag_names = [name.strip().lower() for name in str(tags_input_value).split(',') if name.strip()]
                    print(f"DEBUG (create_post): Parsed tags from string: {tag_names}")  # Debug

                # Chỉ tiếp tục nếu có tên tag hợp lệ sau khi parse
                if tag_names:
                    # Tìm các tag đã tồn tại trong DB
                    existing_tags = Tag.query.filter(Tag.name.in_(tag_names)).all()
                    existing_tags_map = {tag.name: tag for tag in existing_tags}

                    # Lặp qua các tên tag đã parse được
                    for name in tag_names:
                        tag = existing_tags_map.get(name)
                        if not tag:
                            # Tạo tag mới nếu chưa có và add vào session
                            tag = Tag(name=name)
                            db.session.add(tag)
                            # print(f"DEBUG (create_post): Added NEW Tag object '{name}' to session.") # Optional Debug
                        # else:
                        # print(f"DEBUG (create_post): Using existing Tag object '{name}' (ID: {tag.id})") # Optional Debug

                        # Thêm đối tượng Tag (mới hoặc cũ) vào list
                        if isinstance(tag, Tag):  # Đảm bảo là đối tượng Tag hợp lệ
                            post_tags_objects.append(tag)
                        # else:
                        #    print(f"!!! WARNING (create_post): Invalid Tag object for name '{name}'") # Optional Debug

            # Gán danh sách các đối tượng Tag cho relationship của post
            post.tags = post_tags_objects
            print(
                f"DEBUG (create_post): Assigned Tag objects to post.tags (before commit): {[t.name for t in post.tags]}")  # Debug
            # >>>>>>>>>>>>>>>>>> END: KẾT THÚC KHỐI XỬ LÝ TAGS ĐÃ SỬA >>>>>>>>>>>>>>>>>>

            # --- Xử lý Attachments ---
            if post_id_to_assign:  # Chỉ tiếp tục nếu có ID
                if form.attachments.data and form.attachments.data[0].filename != '':
                    # ... (Giữ nguyên code xử lý attachment) ...
                    for file in form.attachments.data:
                        original_filename = secure_filename(file.filename)
                        if original_filename != '':
                            name, ext = os.path.splitext(original_filename)
                            unique_filename = f"{uuid.uuid4().hex}{ext}"
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                            try:
                                file.save(file_path)
                                attachment = Attachment(original_filename=original_filename,
                                                        saved_filename=unique_filename, post_id=post_id_to_assign)
                                attachments_to_add.append(attachment)
                                saved_physical_files.append(file_path)
                                files_saved_count += 1
                            except Exception as file_e:
                                flash(f'Lỗi khi lưu file {original_filename}: {file_e}.', 'warning')

                # Thêm attachments vào session
                if attachments_to_add:
                    db.session.add_all(attachments_to_add)

                # --- Commit cuối cùng ---
                print("DEBUG (create_post): Attempting final commit...")  # Debug
                db.session.commit()  # Lưu post, tags, liên kết, attachments
                print("DEBUG (create_post): Final commit successful!")  # Debug
                flash(f'Bài đăng đã được tạo thành công! ({files_saved_count} tệp đính kèm).', 'success')
                return redirect(url_for('my_posts'))
            else:
                db.session.rollback()
                flash('Lỗi nghiêm trọng: Không thể lấy ID bài đăng.', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Đã xảy ra lỗi khi tạo bài đăng: {e}', 'danger')
            # Xóa file đã lưu nếu commit lỗi
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        print(f"Error deleting file after create fail: {remove_err}")

    elif form.errors:
        print(f"Form validation errors (create_post): {form.errors}")

    # Render template cho GET hoặc khi validation fail
    return render_template('create_post.html', title='Tạo Bài đăng mới', form=form,
                           legend='Tạo Bài đăng / Đề tài', all_tag_names=all_tag_names)


# --- SỬA LẠI ROUTE DOWNLOAD FILE ---
# --- ROUTE DOWNLOAD FILE POST ATTACHMENT (ĐÃ SỬA) ---
@app.route('/uploads/<path:filename>')
@login_required
def download_file(filename):
    # Tìm attachment của Post dựa trên saved_filename
    attachment = Attachment.query.filter_by(saved_filename=filename).first_or_404()
    download_name = attachment.original_filename or filename
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True,
                                   download_name=download_name)
    except FileNotFoundError:
        abort(404)


# --- ROUTE VIEW POST ---
@app.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    # --- LẤY VÀ SẮP XẾP DANH SÁCH SINH VIÊN QUAN TÂM ---
    interested_students_list = []  # Khởi tạo list rỗng
    # Chỉ lấy nếu là đề tài và có relationship
    if post.post_type == 'topic' and hasattr(post, 'interested_students'):
        try:
            # Lấy danh sách và sắp xếp theo tên User A-Z
            # Giả định relationship 'interested_students' là lazy='dynamic'
            interested_students_list = post.interested_students.order_by(User.full_name.asc()).all()
        except Exception as e:
            print(f"Lỗi khi query interested_students cho post {post.id}: {e}")
            interested_students_list = []
    # --- KẾT THÚC LẤY VÀ SẮP XẾP ---

    already_applied = False  # Mặc định là chưa đăng ký
    if current_user.is_authenticated and current_user.role == 'student':
        # Query xem có bản ghi TopicApplication nào khớp không
        existing_app = TopicApplication.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        if existing_app:
            already_applied = True  # Nếu có thì đặt thành True

    # Render template, truyền thêm danh sách students đã sắp xếp
    return render_template('post_detail.html',
                           title=post.title,
                           post=post,
                           # <<< TRUYỀN BIẾN NÀY VÀO TEMPLATE >>>
                           interested_students=interested_students_list)


# --- KẾT THÚC SỬA VIEW_POST ---


# --- ROUTE UPDATE POST (ĐÃ SỬA HOÀN CHỈNH) ---
@app.route('/post/<int:post_id>/update', methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user: abort(403)
    form = PostForm()

    # --- Lấy danh sách tên các tag đã có (cho Tagify whitelist) ---
    # Cần cho cả GET (hiển thị form) và POST (nếu validation fail)
    try:
        all_tags = Tag.query.order_by(Tag.name).all()
        all_tag_names = [tag.name for tag in all_tags]
    except Exception as e:
        print(f"Lỗi khi lấy danh sách tags cho form update: {e}")
        all_tag_names = []
    # --------------------------------------------------------------

    if form.validate_on_submit():
        # --- Cập nhật các trường cơ bản ---
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        post.title = form.title.data
        post.content = safe_content
        post.post_type = form.post_type.data
        post.status = form.status.data
        post.is_featured = form.is_featured.data
        # ---------------------------------

        # Khởi tạo các biến cho attachment
        attachments_to_add = []
        saved_physical_files = []
        files_saved_count = 0  # Sẽ tính lại sau
        old_filenames_to_delete = []
        files_were_uploaded = bool(form.attachments.data and form.attachments.data[0].filename != '')

        try:
            # >>>>>>>>>>>>>>>>>> START: KHỐI XỬ LÝ TAGS ĐÃ SỬA (XỬ LÝ JSON) >>>>>>>>>>>>>>>>>>
            tags_input_value = form.tags.data  # Giá trị từ input (có thể là JSON string)
            post_tags_objects = []  # List để giữ các đối tượng Tag cuối cùng
            tag_names = []  # List để giữ tên tag đã parse

            if tags_input_value:  # Chỉ xử lý nếu có dữ liệu
                try:
                    # THỬ parse dữ liệu đầu vào như là một chuỗi JSON
                    tag_data_list = json.loads(tags_input_value)
                    # Trích xuất tên tag từ key 'value'
                    tag_names = [
                        item['value'].strip().lower()
                        for item in tag_data_list
                        if isinstance(item, dict) and item.get('value') and str(item.get('value')).strip()
                    ]
                    # print(f"DEBUG (update_post): Parsed tags from JSON: {tag_names}") # Optional Debug

                except (json.JSONDecodeError, TypeError, ValueError):
                    # NẾU KHÔNG PHẢI JSON -> Coi như là chuỗi cách nhau bởi dấu phẩy
                    # print(f"DEBUG (update_post): Failed to parse as JSON, treating as comma-separated: '{tags_input_value}'") # Optional Debug
                    tag_names = [name.strip().lower() for name in str(tags_input_value).split(',') if name.strip()]
                    # print(f"DEBUG (update_post): Parsed tags from string: {tag_names}") # Optional Debug

                # Chỉ tiếp tục nếu có tên tag hợp lệ sau khi parse
                if tag_names:
                    # Tìm các tag đã tồn tại trong DB
                    existing_tags = Tag.query.filter(Tag.name.in_(tag_names)).all()
                    existing_tags_map = {tag.name: tag for tag in existing_tags}

                    # Lặp qua các tên tag đã parse được
                    for name in tag_names:
                        tag = existing_tags_map.get(name)
                        if not tag:
                            # Tạo tag mới nếu chưa có và add vào session
                            tag = Tag(name=name)
                            db.session.add(tag)
                        # Thêm đối tượng Tag (mới hoặc cũ) vào list
                        if isinstance(tag, Tag):
                            post_tags_objects.append(tag)

            # Gán lại toàn bộ danh sách tags cho post (SQLAlchemy xử lý M-M update)
            post.tags = post_tags_objects
            # print(f"DEBUG (update_post): Assigned Tag objects to post.tags (before commit): {[t.name for t in post.tags]}") # Optional Debug
            # >>>>>>>>>>>>>>>>>> END: KẾT THÚC KHỐI XỬ LÝ TAGS ĐÃ SỬA >>>>>>>>>>>>>>>>>>

            # --- Xử lý Attachments ---
            if files_were_uploaded:
                # Lấy danh sách file cũ để xóa sau khi commit thành công
                old_filenames_to_delete = [att.saved_filename for att in post.attachments]
                # Xóa các liên kết attachment cũ trong session (chưa xóa file vật lý)
                post.attachments = []
                for file in form.attachments.data:  # Chỉ lặp qua file mới
                    original_filename = secure_filename(file.filename)
                    if original_filename != '':
                        # ... (Code lưu file mới và tạo object Attachment như cũ) ...
                        name, ext = os.path.splitext(original_filename)
                        unique_filename = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        try:
                            file.save(file_path)
                            attachment = Attachment(original_filename=original_filename,
                                                    saved_filename=unique_filename,
                                                    post_id=post.id)  # Gán post_id trực tiếp
                            attachments_to_add.append(attachment)
                            saved_physical_files.append(file_path)
                            files_saved_count += 1
                        except Exception as e:
                            flash(f'Lỗi khi lưu file mới {original_filename}.', 'warning')
            else:
                # Nếu không upload file mới, lấy số lượng file hiện có
                # Query trực tiếp từ DB phòng trường hợp session có thay đổi chưa commit
                try:
                    files_saved_count = db.session.query(Attachment).filter_by(post_id=post.id).count()
                except:  # Tránh lỗi nếu post.id chưa có vì lý do nào đó
                    files_saved_count = 0

            # Add các attachment mới vào session (nếu có)
            if attachments_to_add:
                db.session.add_all(attachments_to_add)

            # --- Commit cuối cùng ---
            # print("DEBUG (update_post): Attempting final commit...") # Optional Debug
            db.session.commit()  # Lưu các thay đổi của post, tags, liên kết tags, attachments mới
            # print("DEBUG (update_post): Final commit successful!") # Optional Debug
            flash(f'Bài đăng đã được cập nhật! ({files_saved_count} tệp đính kèm).', 'success')

            # --- Xóa file vật lý cũ (chỉ khi upload mới thành công) ---
            if files_were_uploaded and old_filenames_to_delete:
                # print(f"DEBUG: Deleting old files: {old_filenames_to_delete}") # Optional Debug
                for filename in old_filenames_to_delete:
                    if filename:
                        old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        if os.path.exists(old_file_path):
                            try:
                                os.remove(old_file_path)
                            except Exception as e:
                                print(f"Update Error deleting old file {old_file_path}: {e}")

            return redirect(url_for('view_post', post_id=post.id))

        except Exception as e:
            db.session.rollback()
            # print(f"!!! DEBUG (update_post): Commit FAILED! Error: {e}") # Optional Debug
            flash(f'Lỗi khi cập nhật bài đăng: {e}', 'danger')
            # Xóa các file vật lý MỚI đã lưu nếu commit bị lỗi
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        print(f"Error deleting NEW file after commit fail: {remove_err}")

    # --- Xử lý GET Request ---
    elif request.method == 'GET':
        # Điền dữ liệu cũ vào form
        form.title.data = post.title
        form.content.data = post.content
        form.post_type.data = post.post_type
        form.status.data = post.status
        form.is_featured.data = post.is_featured
        # Điền tags hiện tại vào ô input (dạng chuỗi) cho Tagify đọc
        current_tags_string = ', '.join([tag.name for tag in post.tags]) if post.tags else ''
        form.tags.data = current_tags_string
    elif form.errors:
        print(f"Form validation errors (update_post): {form.errors}")  # In lỗi validation

    # --- Render template ---
    # Cần truyền cả all_tag_names và current_tags_string cho GET và POST lỗi validation
    current_tags_string = ', '.join([tag.name for tag in post.tags]) if post.tags else ''  # Lấy lại giá trị mới nhất

    return render_template('create_post.html', title='Cập nhật Bài đăng', form=form,
                           legend=f'Cập nhật: {post.title}', post=post,  # Truyền post để hiển thị file cũ
                           all_tag_names=all_tag_names,  # <<< Cho Tagify whitelist
                           current_tags_string=current_tags_string)


# --- ROUTE DELETE POST (Author's Delete) ---
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user: abort(403)
    filenames_to_delete = [att.saved_filename for att in post.attachments]
    try:
        db.session.delete(post)
        db.session.commit()
        for filename in filenames_to_delete:  # Xóa file sau khi commit DB
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error deleting post attachment file {file_path}: {e}")
        flash('Bài đăng của bạn đã được xóa!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa bài đăng: {e}', 'danger')
    return redirect(url_for('my_posts'))


# --- ACCOUNT ROUTES ---
@app.route('/account')
@login_required
def account():
    cohort = None
    if current_user.role == 'student' and current_user.student_id and len(current_user.student_id) >= 2:
        try:
            cohort = f"K{current_user.student_id[:2]}"
        except:
            cohort = "N/A"
    # Nên dùng account_view.html
    return render_template('account_view.html', title='Thông tin Tài khoản', cohort=cohort)


# --- ĐẢM BẢO CÓ HÀM NÀY VÀ ĐẶT NÓ TRƯỚC CÁC ROUTE SỬ DỤNG NÓ ---
def save_picture(form_picture, old_picture_filename=None):
    """Lưu ảnh đại diện người dùng upload (resize, tạo tên unique, xóa ảnh cũ)."""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    # Lấy đường dẫn thư mục user_pics từ config hoặc tạo path
    user_pics_dir = current_app.config.get('USER_PICS_FOLDER',
                                           os.path.join(current_app.root_path, 'static', 'user_pics'))
    picture_path = os.path.join(user_pics_dir, picture_fn)

    # Xóa ảnh cũ
    if old_picture_filename and not old_picture_filename.startswith('default'):
        try:
            old_picture_path = os.path.join(user_pics_dir, old_picture_filename)
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)
        except Exception as e:
            print(f"Lỗi khi xóa ảnh cũ {old_picture_path}: {e}")

    # Resize và lưu ảnh mới
    output_size = (150, 150)
    try:
        img = Image.open(form_picture)
        img.thumbnail(output_size)
        img.save(picture_path)
        return picture_fn
    except Exception as e:
        print(f"Lỗi khi lưu hoặc resize ảnh: {e}")
        return None


# --- KẾT THÚC HÀM ---

@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        new_image_filename = None  # Lưu lại tên file mới
        if form.picture.data:
            picture_file = save_picture(form.picture.data, current_user.image_file)
            if picture_file:
                new_image_filename = picture_file  # Lưu tên file mới vào biến tạm
                current_user.image_file = new_image_filename  # Gán vào đối tượng
                print(f"DEBUG: Assigned new image_file to current_user: {current_user.image_file}")
            else:
                flash('Đã xảy ra lỗi khi tải ảnh lên.', 'danger')

        # Gán các giá trị khác
        current_user.date_of_birth = form.date_of_birth.data
        current_user.gender = form.gender.data
        current_user.phone_number = form.phone_number.data
        # Kiểm tra xem form.contact_email.data có giá trị không, nếu không thì gán None
        current_user.contact_email = form.contact_email.data if form.contact_email.data else None
        current_user.about_me = form.about_me.data
        current_user.class_name = form.class_name.data

        print(
            f"DEBUG: User object state BEFORE commit: ImageFile={current_user.image_file}, Phone={current_user.phone_number}, ...")  # In trạng thái trước commit

        # Commit và Redirect
        try:
            print("DEBUG: Attempting db.session.commit()")
            db.session.commit()  # Cố gắng lưu tất cả thay đổi
            print("DEBUG: Commit successful.")
            flash('Thông tin tài khoản của bạn đã được cập nhật!', 'success')
        except Exception as e:
            db.session.rollback()  # Rollback nếu lỗi
            # <<< QUAN TRỌNG: XEM LỖI Ở ĐÂY >>>
            print(f"!!! DEBUG: Commit FAILED in account_edit! Error: {e}")
            flash(f'Lỗi khi cập nhật thông tin: {e}', 'danger')
            # Nếu lỗi là do ảnh, có thể cần xóa file ảnh vật lý đã lưu?
            # if new_image_filename: # Nếu đã lưu ảnh mới mà commit lỗi
            #    file_path = os.path.join(app.config['USER_PICS_FOLDER'], new_image_filename)
            #    if os.path.exists(file_path): os.remove(file_path)

        return redirect(url_for('account'))
    elif request.method == 'GET':
        # Điền dữ liệu vào form

        form.date_of_birth.data = current_user.date_of_birth
        form.gender.data = current_user.gender
        form.phone_number.data = current_user.phone_number
        form.contact_email.data = current_user.contact_email
        form.about_me.data = current_user.about_me
        form.class_name.data = current_user.class_name
    return render_template('account_edit.html', title='Chỉnh sửa Thông tin', form=form)


# --- STUDENT INTEREST ROUTES ---
@app.route('/interest/add/<int:post_id>', methods=['POST'])
@login_required
def register_interest(post_id):
    if current_user.role != 'student': abort(403)
    post = Post.query.get_or_404(post_id)
    if post.post_type != 'topic' or post.status == 'closed': abort(400)
    is_interested = current_user.interested_topics.filter(student_topic_interest.c.post_id == post.id).count() > 0
    if is_interested:
        flash('Bạn đã quan tâm đề tài này rồi.', 'info')
    else:
        current_user.interested_topics.append(post)
        try:
            db.session.commit()
            flash(f'Đã thêm đề tài "{post.title}" vào danh sách quan tâm!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi đăng ký quan tâm: {e}', 'danger')
    return redirect(request.referrer or url_for('view_post', post_id=post_id))


@app.route('/interest/remove/<int:post_id>', methods=['POST'])
@login_required
def remove_interest(post_id):
    if current_user.role != 'student': abort(403)
    post = Post.query.get_or_404(post_id)
    is_interested = current_user.interested_topics.filter(student_topic_interest.c.post_id == post.id).count() > 0
    if not is_interested:
        flash('Bạn chưa quan tâm đề tài này.', 'info')
    else:
        current_user.interested_topics.remove(post)
        try:
            db.session.commit()
            flash(f'Đã bỏ quan tâm đề tài "{post.title}".', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi bỏ quan tâm: {e}', 'danger')
    return redirect(request.referrer or url_for('view_post', post_id=post_id))


@app.route('/my_interests')
@login_required
def my_interests():
    if current_user.role != 'student': abort(403)
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10
    pagination = current_user.interested_topics.order_by(Post.date_posted.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('interested_topics.html', title='Đề tài đã quan tâm',
                           posts_pagination=pagination)


# --- THÊM ROUTE MỚI ĐỂ ĐỔI MẬT KHẨU ---
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():  # Đã bao gồm kiểm tra mật khẩu hiện tại đúng không
        # Lấy mật khẩu mới và hash nó
        current_user.set_password(form.new_password.data)
        try:
            db.session.commit()  # Lưu mật khẩu hash mới vào DB
            flash('Mật khẩu của bạn đã được cập nhật thành công!', 'success')
            # Chuyển về trang xem hồ sơ sau khi đổi thành công
            return redirect(url_for('account'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật mật khẩu: {e}', 'danger')

    # Hiển thị form cho GET request hoặc khi validation thất bại
    return render_template('change_password.html', title='Đổi Mật khẩu', form=form)


@app.route('/api/search-suggestions')
@login_required  # Vẫn yêu cầu đăng nhập để thấy gợi ý? (Tùy bạn)
def search_suggestions():
    # Lấy từ khóa tìm kiếm từ query parameter 'q'
    query_term = request.args.get('q', '', type=str)
    suggestions = []  # List chứa kết quả gợi ý

    if query_term and len(query_term) >= 2:  # Chỉ tìm khi có từ khóa và đủ dài (vd: >= 2 ký tự)
        search_pattern = f"%{query_term}%"
        # Tìm các bài post có tiêu đề hoặc nội dung khớp (giới hạn số lượng)
        # Join với User để lấy tên tác giả
        posts = Post.query.join(User).filter(
            or_(
                Post.title.ilike(search_pattern),
                Post.content.ilike(search_pattern)
                # Có thể tìm cả theo tên tác giả: User.full_name.ilike(search_pattern)
            )
        ).order_by(Post.date_posted.desc()).limit(10).all()  # Giới hạn 10 kết quả

        # Format kết quả thành list các dictionary
        for post in posts:
            suggestions.append({
                'id': post.id,
                'title': post.title,
                'author': post.author.full_name,
                # Tạo URL đến trang chi tiết post
                'url': url_for('view_post', post_id=post.id)
            })

    # Trả về kết quả dưới dạng JSON
    return jsonify(suggestions)


# --- KẾT THÚC API ENDPOINT ---


@app.route('/search')
@login_required
def search_results():
    # Lấy tất cả tham số từ URL
    search_query = request.args.get('q', '', type=str)
    page = request.args.get('page', 1, type=int)
    selected_sort = request.args.get('sort', 'date_desc')
    selected_author_id = request.args.get('author_id', '', type=str)
    selected_post_type = request.args.get('post_type', '', type=str)
    selected_status = request.args.get('status', '', type=str)

    RESULTS_PER_PAGE = 10

    # Query cơ sở (chỉ tìm bài không nổi bật hoặc tìm tất cả tùy bạn quyết định)
    # Ví dụ: chỉ tìm bài không nổi bật
    query = Post.query.filter_by(is_featured=False)
    # Hoặc tìm tất cả: query = Post.query

    # --- Áp dụng LỌC TÌM KIẾM theo 'q' ---
    if search_query:
        search_term = f"%{search_query}%"
        query = query.join(User, Post.user_id == User.id).filter(  # Join sẵn nếu tìm cả author
            or_(
                Post.title.ilike(search_term),
                Post.content.ilike(search_term),
                User.full_name.ilike(search_term)  # Tìm theo cả tác giả
            )
        )
        needs_join = False  # Đã join rồi
    else:  # Không có tìm kiếm 'q'
        needs_join = bool(selected_author_id)  # Chỉ join nếu lọc theo author
        if needs_join: query = query.join(User, Post.user_id == User.id)

    # --- Áp dụng các bộ lọc khác ---
    if selected_author_id: query = query.filter(User.id == selected_author_id)
    if selected_post_type: query = query.filter(Post.post_type == selected_post_type)
    if selected_post_type == 'topic' and selected_status: query = query.filter(Post.status == selected_status)

    # --- Áp dụng Sắp xếp ---
    if selected_sort == 'date_asc':
        query = query.order_by(Post.date_posted.asc())
    elif selected_sort == 'title_asc':
        query = query.order_by(asc(db.func.lower(Post.title)))
    elif selected_sort == 'title_desc':
        query = query.order_by(desc(db.func.lower(Post.title)))
    else:
        query = query.order_by(Post.date_posted.desc())

    # Phân trang
    search_pagination = query.paginate(page=page, per_page=RESULTS_PER_PAGE, error_out=False)

    # Lấy danh sách Giảng viên
    lecturers = User.query.filter_by(role='lecturer').order_by(User.full_name).all()

    # Render template và truyền đủ dữ liệu
    return render_template('search_results.html',
                           title=f"Kết quả tìm kiếm cho '{search_query}'" if search_query else "Tìm kiếm",
                           q=search_query,  # Truyền lại từ khóa
                           posts_pagination=search_pagination,  # Đổi tên biến này cho nhất quán với template
                           lecturers=lecturers,
                           selected_sort=selected_sort,
                           selected_author_id=selected_author_id,
                           selected_post_type=selected_post_type,
                           selected_status=selected_status
                           )


@app.route('/idea/submit', methods=['GET', 'POST'])
@login_required
def submit_idea():
    if current_user.role != 'student':
        flash('Chỉ sinh viên mới có thể gửi ý tưởng.', 'warning')
        return redirect(url_for('dashboard'))
    form = IdeaSubmissionForm()
    try:  # Lấy choices bên ngoài if validate
        lecturer_choices = [(l.id, l.full_name) for l in
                            User.query.filter_by(role='lecturer').order_by(User.full_name).all()]
        form.recipients.choices = lecturer_choices
    except Exception as e:
        flash('Lỗi tải danh sách giảng viên.', 'danger')
        form.recipients.choices = []

    if form.validate_on_submit():
        safe_description = bleach.clean(form.description.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        idea = StudentIdea(title=form.title.data, description=safe_description, student=current_user)
        idea_id_to_assign = None
        saved_physical_files = []
        attachments_to_add = []
        files_saved_count = 0
        try:
            db.session.add(idea)
            # Xử lý recipients ngay sau khi add idea vào session
            selected_recipient_ids = form.recipients.data
            if selected_recipient_ids:
                recipients_to_add = User.query.filter(User.id.in_(selected_recipient_ids),
                                                      User.role == 'lecturer').all()
                idea.recipients = recipients_to_add
            else:
                idea.recipients = []

            db.session.flush()  # Flush để lấy ID và kiểm tra recipients trước khi xử lý file
            idea_id_to_assign = idea.id

            # >>>>>>>>>>>>>>>>>> START: THÊM CODE XỬ LÝ TAGS Ở ĐÂY >>>>>>>>>>>>>>>>>>
            tags_string = form.tags.data
            post_tags_objects = []  # List để giữ các đối tượng Tag
            if tags_string:
                # Tách chuỗi thành list tên tag, xóa khoảng trắng, chuyển về chữ thường
                tag_names = [name.strip().lower() for name in tags_string.split(',') if name.strip()]
                if tag_names:
                    # Lấy các tag đã tồn tại trong DB ứng với các tên trong list
                    existing_tags = Tag.query.filter(Tag.name.in_(tag_names)).all()
                    # Tạo một map để truy cập nhanh tag đã có theo tên
                    existing_tags_map = {tag.name: tag for tag in existing_tags}

                    for name in tag_names:
                        tag = existing_tags_map.get(name)  # Lấy tag từ map nếu có
                        if not tag:
                            # Nếu tag chưa có trong DB, tạo mới và add vào session
                            tag = Tag(name=name)
                            db.session.add(tag)
                        # Thêm tag (dù mới hay cũ) vào list cho bài post này
                        post_tags_objects.append(tag)

            # Gán danh sách các đối tượng Tag vào relationship của post
            # SQLAlchemy sẽ tự xử lý việc thêm vào bảng liên kết post_tags khi commit
            post.tags = post_tags_objects

            # Xử lý file attachments nếu có ID
            if form.attachments.data and form.attachments.data[0].filename != '':
                for file in form.attachments.data:
                    original_filename = secure_filename(file.filename)
                    if original_filename != '':
                        name, ext = os.path.splitext(original_filename)
                        unique_filename = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        try:
                            file.save(file_path)
                            attachment = IdeaAttachment(original_filename=original_filename,
                                                        saved_filename=unique_filename, idea_id=idea_id_to_assign)
                            attachments_to_add.append(attachment)
                            saved_physical_files.append(file_path)
                            files_saved_count += 1
                        except Exception as file_e:
                            flash(f'Lỗi khi lưu file {original_filename}.', 'warning')
                            print(f"Error saving file {original_filename}: {file_e}")

            # Commit cuối cùng
            if attachments_to_add:
                db.session.add_all(attachments_to_add)
            db.session.commit()
            try:
                # Lấy danh sách giảng viên đã được liên kết với ý tưởng
                # Giả sử 'idea.recipients' vẫn chứa đúng danh sách sau commit
                lecturers_to_notify = idea.recipients

                if lecturers_to_notify:  # Chỉ tạo thông báo nếu có người nhận
                    notifications_to_add = []
                    for lecturer in lecturers_to_notify:
                        # Tạo nội dung thông báo (bạn có thể tùy chỉnh)
                        notification_content = f"Sinh viên {current_user.full_name} đã gửi một ý tưởng mới: '{idea.title}'"

                        # Tạo đối tượng Notification
                        # !!! Quan trọng: Đảm bảo các tên trường khớp với model Notification của bạn !!!
                        new_notification = Notification(
                            recipient_id=lecturer.id,  # ID người nhận (giảng viên)
                            sender_id=current_user.id,  # ID người gửi (sinh viên)
                            content=notification_content,  # Nội dung thông báo
                            notification_type='new_idea',  # Loại thông báo (ví dụ)
                            related_idea_id=idea.id,  # ID của ý tưởng liên quan
                            is_read=False  # Mặc định là chưa đọc
                            # timestamp: Thường DB hoặc Model sẽ tự xử lý
                        )
                        notifications_to_add.append(new_notification)

                    # Thêm tất cả thông báo mới vào session và commit
                    if notifications_to_add:
                        db.session.add_all(notifications_to_add)
                        db.session.commit()  # Commit các bản ghi thông báo

            except Exception as notif_e:
                # Xử lý lỗi nếu không tạo được thông báo
                # Bạn có thể chọn rollback cả giao dịch chính hoặc chỉ log lỗi
                # và báo cho người dùng biết (ví dụ: bằng flash message)
                print(f"LỖI NGHIÊM TRỌNG khi tạo thông báo cho ý tưởng ID {idea.id}: {notif_e}")
                # Có thể cân nhắc rollback ở đây nếu việc tạo thông báo là bắt buộc
                # db.session.rollback()
                flash('Gửi ý tưởng thành công, nhưng có lỗi xảy ra khi tạo thông báo cho giảng viên.', 'warning')

            flash(f'Ý tưởng của bạn đã được gửi thành công! ({files_saved_count} tệp đính kèm).', 'success')
            redirect_target = 'my_ideas' if 'my_ideas' in app.view_functions else 'dashboard'
            return redirect(url_for(redirect_target))

        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi gửi ý tưởng: {e}', 'danger')
            # Xóa file vật lý đã lưu nếu commit lỗi
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        print(f"Error deleting file after commit fail: {remove_err}")

    # Render form cho GET hoặc validation fail
    # Đảm bảo choices vẫn còn nếu validation fail ở POST
    if request.method == 'POST' and not form.validate_on_submit():
        print("Form validation errors (submit_idea):", form.errors)
        # Choices đã được đặt ở đầu hàm nên vẫn còn
    return render_template('submit_idea.html', title='Gửi Ý tưởng Mới', form=form)


@app.route('/idea_uploads/<path:filename>')
@login_required
def download_idea_attachment(filename):
    attachment = IdeaAttachment.query.filter_by(saved_filename=filename).first_or_404()
    # Add authorization if needed
    download_name = attachment.original_filename or filename
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True,
                                   download_name=download_name)
    except FileNotFoundError:
        abort(404)


@app.route('/my-ideas')
@login_required
def my_ideas():
    if current_user.role != 'student': abort(403)

    # --- Query Ý tưởng Đang chờ duyệt ---
    pending_ideas_query = StudentIdea.query.filter_by(
        student=current_user,  # Lọc theo sinh viên hiện tại
        status='pending'  # Lọc theo trạng thái
    ).order_by(StudentIdea.submission_date.desc())
    pending_ideas = pending_ideas_query.all()  # Lấy tất cả (tạm thời chưa phân trang)

    # --- Query Ý tưởng Đã phản hồi ---
    responded_ideas_query = StudentIdea.query.filter(
        StudentIdea.student == current_user,  # Lọc theo sinh viên hiện tại
        StudentIdea.status != 'pending'  # Lọc các trạng thái KHÁC pending
    ).order_by(StudentIdea.submission_date.desc())
    responded_ideas = responded_ideas_query.all()  # Lấy tất cả (tạm thời chưa phân trang)

    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10
    pagination = StudentIdea.query.filter_by(student=current_user).order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)  # Corrected query
    # Truyền cả 2 danh sách vào template
    return render_template('my_ideas.html',  # <<< Giữ nguyên tên template này
                           title='Ý tưởng của tôi',
                           pending_ideas=pending_ideas,
                           responded_ideas=responded_ideas)


@app.route('/my-ideas/<int:idea_id>')
@login_required
def view_my_idea(idea_id):
    idea = StudentIdea.query.get_or_404(idea_id)
    if idea.student_id != current_user.id: abort(403)
    return render_template('view_my_idea.html', title=idea.title, idea=idea)


@app.route('/my-ideas/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_my_idea(idea_id):
    idea = StudentIdea.query.get_or_404(idea_id)
    if idea.student_id != current_user.id: abort(403)
    filenames_to_delete = [att.saved_filename for att in idea.attachments]
    try:
        db.session.delete(idea)
        db.session.commit()
        for filename in filenames_to_delete:  # Delete files after successful DB commit
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error deleting idea attachment file {file_path}: {e}")
        flash('Ý tưởng của bạn đã được xóa!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa ý tưởng: {e}', 'danger')
    return redirect(url_for('my_ideas'))


@app.route('/pending-ideas')  # Hoặc @admin_bp.route('/pending-ideas')

@login_required
def view_pending_ideas():
    # Kiểm tra quyền (GV hoặc Admin)
    if current_user.role not in ['lecturer', 'admin']:
        abort(403)

    page = request.args.get('page', 1, type=int)
    PER_PAGE = 15

    # Xây dựng Query
    query = StudentIdea.query.filter(
        StudentIdea.status == 'pending',  # Lọc status trước
        # Thêm điều kiện lọc người nhận:
        # KHÔNG PHẢI là ( (Có người nhận cụ thể) VÀ (Tôi KHÔNG phải người nhận) )
        ~(
                StudentIdea.recipients.any() &  # Có người nhận VÀ
                ~StudentIdea.recipients.any(User.id == current_user.id)  # Tôi không nằm trong đó
        )
    )

    # Sắp xếp và Phân trang
    pagination = query.order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template('view_ideas_list.html',  # Đảm bảo đúng tên template
                           title='Ý tưởng Chờ Duyệt',
                           ideas_pagination=pagination,
                           list_title='Danh sách Ý tưởng Chờ Duyệt',
                           active_tab='pending')  # Truyền tab nếu template dùng tabs


@app.route('/idea/<int:idea_id>/review', methods=['GET', 'POST'])
@login_required
def review_idea(idea_id):
    if current_user.role != 'lecturer':
        abort(403)

    idea = StudentIdea.query.get_or_404(idea_id)
    form = IdeaReviewForm()

    if form.validate_on_submit():  # Xử lý POST
        original_status = idea.status  # Lưu trạng thái cũ

        # Cập nhật đối tượng idea trong session (chưa commit)
        idea.status = form.status.data
        idea.feedback = form.feedback.data
        # idea.reviewer_id = current_user.id # Nếu có

        notification_to_add = None  # Chuẩn bị biến cho notification
        # Chỉ tạo thông báo nếu trạng thái thay đổi hoặc có phản hồi mới
        if idea.status != original_status or form.feedback.data:
            status_text = {
                'approved': 'được chấp thuận', 'rejected': 'bị từ chối',
                'reviewed': 'đã được xem xét', 'pending': 'quay lại chờ duyệt'
            }.get(idea.status, f'cập nhật thành {idea.status}')
            feedback_text = " và có phản hồi mới" if form.feedback.data else ""
            notif_content = f"Ý tưởng \"{idea.title[:30]}...\" của bạn đã {status_text}{feedback_text}."

            print(f"DEBUG: Preparing notification for User ID: {idea.student_id}")  # DEBUG
            # Tạo đối tượng Notification nhưng chưa add vào session ngay
            notification_to_add = Notification(content=notif_content,
                                               recipient_id=idea.student_id,
                                               related_idea_id=idea.id)

        try:
            # Chỉ add notification vào session nếu nó được tạo
            if notification_to_add:
                db.session.add(notification_to_add)
                print("DEBUG: Notification added to session.")  # DEBUG

            # Commit một lần duy nhất cho cả cập nhật Idea và thêm Notification
            db.session.commit()
            print("DEBUG: db.session.commit() successful.")  # DEBUG
            flash(f'Đã cập nhật trạng thái và phản hồi cho ý tưởng "{idea.title}".', 'success')

            # Chuyển hướng dựa trên trạng thái MỚI
            if idea.status == 'pending':
                # Nếu GV vô tình đặt lại là pending, quay về ds pending
                return redirect(url_for('view_pending_ideas'))
            else:
                # Nếu trạng thái là reviewed, approved, rejected, chuyển về ds đã phản hồi
                # Đảm bảo bạn đã tạo route 'view_responded_ideas'
                redirect_target = 'view_responded_ideas' if 'view_responded_ideas' in app.view_functions else 'view_pending_ideas'
                return redirect(url_for(redirect_target))

        except Exception as e:
            db.session.rollback()  # Rollback tất cả thay đổi nếu có lỗi
            print(f"!!! Error during commit: {e}")  # DEBUG
            flash(f'Lỗi khi cập nhật ý tưởng: {e}', 'danger')
            # Không cần return render_template ở đây vì sẽ chạy xuống dưới

    elif request.method == 'GET':  # Xử lý GET
        form.status.data = idea.status
        form.feedback.data = idea.feedback

    # Render template cho GET hoặc khi POST validation fail
    return render_template('review_idea.html', title=f"Review: {idea.title}",
                           idea=idea, form=form)


# --- THÊM ROUTE GIẢNG VIÊN XÓA Ý TƯỞNG ---
@app.route('/idea/<int:idea_id>/delete-by-lecturer', methods=['POST'])
@login_required
def delete_idea_by_lecturer(idea_id):
    # Chỉ giảng viên mới được xóa (hoặc sau này là Admin)
    if current_user.role != 'lecturer':
        abort(403)

    idea = StudentIdea.query.get_or_404(idea_id)

    # Lấy danh sách tên file cần xóa vật lý
    filenames_to_delete = [att.saved_filename for att in idea.attachments]

    try:
        # Xóa idea (cascade sẽ xóa IdeaAttachment records)
        db.session.delete(idea)
        db.session.commit()

        # Xóa file vật lý sau khi commit DB thành công
        for filename in filenames_to_delete:
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"GV Deleted file: {file_path}")  # DEBUG
                    except Exception as e:
                        print(f"Error deleting file {file_path} by lecturer: {e}")

        flash('Ý tưởng đã được xóa thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Đã xảy ra lỗi khi xóa ý tưởng: {e}', 'danger')

    # Chuyển hướng về trang danh sách ý tưởng chờ duyệt (hoặc trang trước đó?)
    return redirect(url_for('view_pending_ideas'))


@app.route('/responded-ideas')
@login_required
def view_responded_ideas():
    # Kiểm tra quyền
    if current_user.role not in ['lecturer', 'admin']:
        abort(403)

    page = request.args.get('page', 1, type=int)
    PER_PAGE = 15

    # Xây dựng Query
    query = StudentIdea.query.filter(
        StudentIdea.status != 'pending',  # Lấy status khác pending
        # Thêm điều kiện lọc người nhận:
        ~(
                StudentIdea.recipients.any() &  # Có người nhận VÀ
                ~StudentIdea.recipients.any(User.id == current_user.id)  # Tôi không nằm trong đó
        )
    )

    # Sắp xếp và Phân trang
    pagination = query.order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Render template
    return render_template('view_ideas_list.html',  # Dùng chung template
                           title='Ý tưởng Đã Phản hồi',
                           ideas_pagination=pagination,
                           list_title='Danh sách Ý tưởng Đã Phản hồi',
                           active_tab='responded')  # Truyền tab nếu template dùng tabs


@app.context_processor
def inject_notifications():
    unread_count = 0
    if current_user.is_authenticated:
        try:  # Thêm try-except để tránh lỗi nếu DB có vấn đề
            unread_count = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        except Exception as e:
            print(f"Lỗi khi đếm thông báo chưa đọc: {e}")
            unread_count = 0  # Hoặc giá trị khác để báo lỗi
    return dict(unread_count=unread_count)


@app.route('/notifications')
@login_required
def notifications():
    # --- Đánh dấu tất cả là đã đọc KHI truy cập trang ---
    # Lấy các thông báo CHƯA ĐỌC của user hiện tại
    unread_notifications = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).all()
    # Đặt is_read = True cho chúng
    for notif in unread_notifications:
        notif.is_read = True
    # Commit thay đổi trạng thái đã đọc vào DB
    try:
        # Chỉ commit nếu có thông báo chưa đọc để tránh commit không cần thiết
        if unread_notifications:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Lỗi khi đánh dấu thông báo đã đọc: {e}")
        flash("Có lỗi xảy ra khi cập nhật trạng thái thông báo.", "warning")
    # --- Kết thúc đánh dấu đã đọc ---

    # --- Lấy danh sách TẤT CẢ thông báo để hiển thị (có phân trang) ---
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 15  # Số thông báo mỗi trang

    # Truy vấn tất cả thông báo của user, sắp xếp mới nhất trước, phân trang
    pagination = Notification.query.filter_by(recipient_id=current_user.id) \
        .order_by(Notification.timestamp.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Render template mới, truyền đối tượng pagination
    return render_template('notifications.html', title='Thông báo của bạn',
                           notifications_pagination=pagination)


@app.route('/notification/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    # Đảm bảo user chỉ xóa được thông báo của chính mình
    if notif.recipient_id != current_user.id:
        abort(403)

    try:
        db.session.delete(notif)
        db.session.commit()
        flash('Đã xóa thông báo.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa thông báo: {e}', 'danger')

    # Chuyển hướng lại trang thông báo (có thể cần tham số trang nếu đang phân trang)
    # Cách đơn giản là về trang 1
    return redirect(url_for('notifications'))


@app.route('/notifications/delete-all', methods=['POST'])
@login_required
def delete_all_notifications():
    try:
        # Sử dụng delete() của query để xóa hiệu quả hơn là lấy hết rồi lặp
        num_deleted = Notification.query.filter_by(recipient_id=current_user.id).delete()
        db.session.commit()
        if num_deleted > 0:
            flash(f'Đã xóa {num_deleted} thông báo.', 'success')
        else:
            flash('Không có thông báo nào để xóa.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa tất cả thông báo: {e}', 'danger')

    return redirect(url_for('notifications'))


@app.route('/apply-topic/<int:post_id>', methods=['POST'])  # Chỉ chấp nhận POST
@login_required
def apply_to_topic(post_id):
    # 1. Kiểm tra vai trò người dùng
    if current_user.role != 'student':
        flash('Chỉ sinh viên mới có thể đăng ký đề tài.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))  # Quay lại trang trước đó

    # 2. Lấy thông tin Post
    post = Post.query.get_or_404(post_id)

    # 3. Kiểm tra điều kiện của Post
    if post.post_type != 'topic' or post.status != 'recruiting':
        flash('Đề tài này không hợp lệ hoặc không còn mở đăng ký.', 'warning')
        return redirect(url_for('view_post', post_id=post_id))

    # 4. Kiểm tra xem sinh viên đã đăng ký chưa
    existing_app = TopicApplication.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing_app:
        flash('Bạn đã đăng ký đề tài này rồi.', 'info')
        return redirect(url_for('view_post', post_id=post.id))

    # 5. Tạo bản ghi đăng ký mới
    application = TopicApplication(user_id=current_user.id, post_id=post.id)
    # (Tùy chọn) Có thể lấy message từ form nếu bạn thêm field message vào form đăng ký
    # application.message = request.form.get('message', None)

    # 6. Tạo thông báo cho Giảng viên (tác giả bài post)
    notification_content = f"Sinh viên {current_user.full_name} đã đăng ký đề tài: '{post.title}'"
    # Giả định Notification model đã có sender_id và notification_type
    # Nếu muốn link trực tiếp đến Post, cần thêm related_post_id vào Notification model
    new_notification = Notification(
        recipient_id=post.user_id,
        sender_id=current_user.id,
        content=notification_content,
        notification_type='topic_application',  # Loại thông báo mới
        # related_post_id=post.id, # <<< Cần thêm trường này vào Notification model và migrate
        is_read=False
    )

    try:
        db.session.add(application)
        db.session.add(new_notification)
        db.session.commit()
        flash('Bạn đã đăng ký thành công đề tài!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Đã xảy ra lỗi khi đăng ký: {e}', 'danger')

    # 7. Chuyển hướng lại trang chi tiết bài đăng
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/my-posts')
@login_required
def my_posts():
    # Có thể cho phép cả Admin xem bài của họ nếu cần, tạm thời chỉ Giảng viên
    if current_user.role != 'lecturer':
        # Hoặc có thể chỉ trả về trang trống thay vì abort
        flash('Chức năng này dành cho Giảng viên.', 'info')
        return redirect(url_for('dashboard'))
        # abort(403)

    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10  # Số bài đăng mỗi trang

    # Truy vấn các bài đăng/đề tài mà user hiện tại là tác giả
    pagination = Post.query.filter_by(author=current_user) \
        .order_by(Post.date_posted.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)

    breadcrumbs = [
        {'url': url_for('dashboard'), 'title': 'Trang chủ'},
        {'url': None, 'title': 'Bài đăng của tôi'}  # Mục cuối không cần url
    ]

    # Render template mới, truyền đối tượng pagination
    return render_template('my_posts.html', title='Bài đăng của tôi',
                           posts_pagination=pagination)

    # Phần chạy ứng dụng

    if __name__ == '__main__':
        app.run(debug=True)


@app.route('/post/<int:post_id>/applications')
@login_required
def view_topic_applications(post_id):
    # Lấy thông tin bài đăng/đề tài
    post = Post.query.get_or_404(post_id)

    # --- Kiểm tra quyền ---
    # Chỉ tác giả của bài đăng (hoặc Admin nếu muốn) mới xem được đơn đăng ký
    if post.author != current_user:  # and current_user.role != 'admin':
        abort(403)  # Báo lỗi không có quyền truy cập

    # --- Kiểm tra loại bài đăng ---
    # Đảm bảo đây là đề tài mới cho phép đăng ký
    if post.post_type != 'topic':
        flash('Chức năng này chỉ áp dụng cho Đề tài Nghiên cứu.', 'warning')
        return redirect(url_for('view_post', post_id=post.id))  # Quay lại trang post

    # --- Lấy danh sách đơn đăng ký ---
    # Sử dụng relationship 'applications' từ Post model (được tạo bởi backref)
    # Sắp xếp theo ngày đăng ký, mới nhất trước hoặc cũ nhất trước tùy bạn chọn
    try:
        applications = post.applications.order_by(TopicApplication.application_date.asc()).all()
    except Exception as e:
        print(f"Lỗi khi query applications cho post {post.id}: {e}")
        applications = []
        flash("Lỗi khi tải danh sách đơn đăng ký.", "danger")

    return render_template('topic_applications.html',  # <<< Tên file template mới
                           title=f"Đơn đăng ký: {post.title}",
                           post=post,
                           applications=applications)


@app.route('/application/<int:application_id>/update_status', methods=['POST'])
@login_required
def update_application_status(application_id):
    # Lấy đơn đăng ký
    application = TopicApplication.query.get_or_404(application_id)
    post = application.topic # Lấy post liên quan từ relationship

    # --- Kiểm tra quyền ---
    # Chỉ tác giả của bài đăng mới được duyệt
    if post.author != current_user: # and current_user.role != 'admin':
        abort(403)

    # Lấy trạng thái mới từ form submit
    new_status = request.form.get('status')

    # Kiểm tra giá trị status hợp lệ
    if new_status not in ['accepted', 'rejected']:
        flash('Trạng thái cập nhật không hợp lệ.', 'danger')
        return redirect(url_for('view_topic_applications', post_id=post.id))

    # Cập nhật trạng thái của đơn đăng ký
    application.status = new_status

    # --- (Tùy chọn) Cập nhật trạng thái của Post ---
    # Ví dụ: Nếu chấp thuận SV đầu tiên, chuyển Post sang 'working_on'?
    # Hoặc nếu đủ số lượng SV mong muốn, chuyển sang 'closed'?
    # Cần logic phức tạp hơn nếu muốn tự động hóa việc này. Ví dụ đơn giản:
    if new_status == 'accepted':
         # Có thể thêm logic kiểm tra số lượng đã accept, nếu đủ thì đổi post.status
         # if post.applications.filter_by(status='accepted').count() >= post.max_students: # Giả sử có max_students
         #    post.status = 'working_on' # Hoặc 'closed'
         pass # Tạm thời chưa đổi status post

    # ------------------------------------------------

    # --- Tạo thông báo cho Sinh viên ---
    student_recipient = application.student
    if student_recipient:
        status_text = "chấp thuận" if new_status == 'accepted' else "từ chối"
        notif_content = f"Đăng ký của bạn cho đề tài \"{post.title[:30]}...\" đã được {status_text}."

        new_notification = Notification(
            recipient_id=student_recipient.id,
            sender_id=current_user.id, # Người gửi là Giảng viên
            content=notif_content,
            notification_type='application_update', # Loại thông báo mới
            # related_post_id=post.id, # <<< Cần thêm trường này vào Notification
            # related_application_id=application.id, # <<< Hoặc trường này?
            is_read=False
        )
        db.session.add(new_notification)
    # ---------------------------------

    try:
        db.session.commit() # Lưu thay đổi status application và notification mới
        flash(f'Đã cập nhật trạng thái đơn đăng ký thành "{new_status}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi cập nhật trạng thái: {e}', 'danger')

    # Chuyển hướng lại trang danh sách đơn đăng ký của post đó
    return redirect(url_for('view_topic_applications', post_id=post.id))
