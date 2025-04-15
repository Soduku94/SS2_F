# app.py

# import các thứ
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
from werkzeug.utils import secure_filename

from models import StudentIdea, Notification

# Import Extensions (Một lần)
from extensions import db, migrate, bcrypt, login_manager

# Import Models (Một lần)
from models import (User, Post, Attachment, StudentIdea, IdeaAttachment, Notification,
                    student_topic_interest, idea_recipient_lecturers)  # Đảm bảo đủ

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
# --- KẾT THÚC CẬP NHẬT ĐƯỜNG DẪN ---

# Cấu hình Upload chung (giữ nguyên)
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
    return User.query.get(int(user_id))


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
            flash(f'Đăng nhập thành công cho {user.full_name}!', 'success')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Đăng nhập thất bại. Vui lòng kiểm tra email và mật khẩu.', 'danger')
            print("DEBUG: Flashed 'Login Failed' message.")
    return render_template('login.html', title='Đăng nhập', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Chuyển hướng nếu đã đăng nhập
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm() # Dùng form đã cập nhật
    if form.validate_on_submit():
        # Hash mật khẩu
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        # Tạo đối tượng User mới với ĐẦY ĐỦ thông tin từ form
        user = User(
            full_name=form.full_name.data,
            student_id=form.student_id.data,
            email=form.email.data,              # Email đăng nhập
            class_name=form.class_name.data,      # Lớp học
            date_of_birth=form.date_of_birth.data, # Ngày sinh
            gender=form.gender.data,            # Giới tính
            phone_number=form.phone_number.data,  # Số điện thoại
            password_hash=hashed_password,
            role='student' # <<< Luôn đặt role là 'student' cho form này
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
    flash('Bạn đã đăng xuất.', 'info')
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


# --- KẾT THÚC ROUTE DASHBOARD ---


# --- ROUTE CREATE POST (ĐÃ SỬA HOÀN CHỈNH) ---
@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.role != 'lecturer':
        flash('Bạn không có quyền truy cập chức năng này.', 'danger')
        return redirect(url_for('dashboard'))

    form = PostForm()
    if form.validate_on_submit():
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        post = Post(title=form.title.data, content=safe_content, post_type=form.post_type.data,
                    is_featured=form.is_featured.data, status=form.status.data, author=current_user)
        post_id_to_assign = None
        try:
            db.session.add(post)
            db.session.flush()
            post_id_to_assign = post.id
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi tạo bài đăng: {e}', 'danger')
            return render_template('create_post.html', title='Tạo Bài đăng mới', form=form,
                                   legend='Tạo Bài đăng / Đề tài')

        if post_id_to_assign:
            files_saved_count = 0
            attachments_to_add = []
            saved_physical_files = []
            if form.attachments.data and form.attachments.data[0].filename != '':
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
                        except Exception as e:
                            flash(f'Lỗi khi lưu file {original_filename}.', 'warning')
            try:
                if attachments_to_add:
                    db.session.add_all(attachments_to_add)
                db.session.commit()
                flash(f'Bài đăng đã được tạo thành công! ({files_saved_count} tệp đính kèm).', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Lỗi khi lưu bài đăng vào database: {e}', 'danger')
                for file_path in saved_physical_files:  # Xóa file đã lưu nếu commit lỗi
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as remove_err:
                            print(f"Error deleting file after commit fail: {remove_err}")
        else:
            flash('Lỗi nghiêm trọng khi tạo bài đăng, không lấy được ID.', 'danger')

    elif form.errors:
        print("Form validation errors (create_post):", form.errors)
    return render_template('create_post.html', title='Tạo Bài đăng mới', form=form, legend='Tạo Bài đăng / Đề tài')


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
    if form.validate_on_submit():
        safe_content = bleach.clean(form.content.data, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        post.title = form.title.data
        post.content = safe_content
        post.post_type = form.post_type.data
        post.status = form.status.data
        post.is_featured = form.is_featured.data

        new_files = form.attachments.data
        files_were_uploaded = bool(new_files and new_files[0].filename != '')
        old_filenames_to_delete = []
        attachments_to_add = []
        saved_physical_files = []
        files_saved_count = 0

        if files_were_uploaded:
            old_filenames_to_delete = [att.saved_filename for att in post.attachments]
            post.attachments = []  # Xóa relationship cũ khỏi session
            for file in new_files:
                original_filename = secure_filename(file.filename)
                if original_filename != '':
                    name, ext = os.path.splitext(original_filename)
                    unique_filename = f"{uuid.uuid4().hex}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    try:
                        file.save(file_path)
                        attachment = Attachment(original_filename=original_filename, saved_filename=unique_filename,
                                                post_id=post.id)
                        attachments_to_add.append(attachment)
                        saved_physical_files.append(file_path)  # Chỉ lưu file mới
                        files_saved_count += 1
                    except Exception as e:
                        flash(f'Lỗi khi lưu file mới {original_filename}.', 'warning')
        else:
            files_saved_count = len(post.attachments)  # Số lượng file giữ nguyên

        try:
            if attachments_to_add:  # Chỉ add nếu có attachment mới
                db.session.add_all(attachments_to_add)
            db.session.commit()  # Commit tất cả thay đổi
            flash(f'Bài đăng đã được cập nhật! ({files_saved_count} tệp đính kèm).', 'success')

            if files_were_uploaded and old_filenames_to_delete:  # Chỉ xóa file cũ nếu upload mới thành công
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
            flash(f'Lỗi khi cập nhật bài đăng: {e}', 'danger')
            # Xóa file vật lý MỚI đã lưu nếu commit lỗi
            for file_path in saved_physical_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as remove_err:
                        print(f"Error deleting NEW file after commit fail: {remove_err}")

    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
        form.post_type.data = post.post_type
        form.status.data = post.status
        form.is_featured.data = post.is_featured
    elif form.errors:
        print("Form validation errors (update_post):", form.errors)

    return render_template('create_post.html', title='Cập nhật Bài đăng', form=form, legend=f'Cập nhật: {post.title}',
                           post=post)


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
    return redirect(url_for('dashboard'))


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
    user_pics_dir = current_app.config.get('USER_PICS_FOLDER', os.path.join(current_app.root_path, 'static', 'user_pics'))
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
        new_image_filename = None # Lưu lại tên file mới
        if form.picture.data:
            picture_file = save_picture(form.picture.data, current_user.image_file)
            if picture_file:
                new_image_filename = picture_file # Lưu tên file mới vào biến tạm
                current_user.image_file = new_image_filename # Gán vào đối tượng
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

        print(f"DEBUG: User object state BEFORE commit: ImageFile={current_user.image_file}, Phone={current_user.phone_number}, ...") # In trạng thái trước commit

        # Commit và Redirect
        try:
            print("DEBUG: Attempting db.session.commit()")
            db.session.commit() # Cố gắng lưu tất cả thay đổi
            print("DEBUG: Commit successful.")
            flash('Thông tin tài khoản của bạn đã được cập nhật!', 'success')
        except Exception as e:
            db.session.rollback() # Rollback nếu lỗi
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
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10
    pagination = StudentIdea.query.filter_by(student=current_user).order_by(StudentIdea.submission_date.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)  # Corrected query
    return render_template('my_ideas.html', title='Ý tưởng của tôi', ideas_pagination=pagination)


@app.route('/my-ideas/<int:idea_id>')
@login_required
def view_my_idea(idea_id):
    idea = StudentIdea.query.get_or_404(idea_id)
    if idea.student_id != current_user.id: abort(403)
    return render_template('view_my_idea.html', title=idea.title, idea=idea)


# --- THÊM ROUTE XÓA Ý TƯỞNG CỦA SINH VIÊN ---
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


# --- THÊM ROUTE CHO GIẢNG VIÊN XEM Ý TƯỞNG PENDING ---
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


# --- KẾT THÚC HÀM PENDING ---


# --- THÊM ROUTE CHO GIẢNG VIÊN REVIEW Ý TƯỞNG ---


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

    # Render template mới, truyền đối tượng pagination
    return render_template('my_posts.html', title='Bài đăng của tôi',
                           posts_pagination=pagination)


# Phần chạy ứng dụng


if __name__ == '__main__':
    app.run(debug=True)
