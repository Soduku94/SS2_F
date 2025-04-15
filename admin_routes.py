

# admin_routes.py
import os
from functools import wraps

# admin_routes.py
import os
from functools import wraps

# Import từ Flask
from flask import Blueprint, request, render_template, abort, flash, redirect, url_for

# Import từ Flask-Login
from flask_login import login_required, current_user

# Import từ SQLAlchemy
from sqlalchemy import or_, asc, desc

import app
# Import từ extensions
from extensions import db, bcrypt

# Import từ models
from models import User, Post, StudentIdea, Attachment, IdeaAttachment # Đảm bảo đủ các model cần dùng

# Import từ forms
from forms import AdminUserCreateForm, AdminUserUpdateForm, IdeaReviewForm





# Tạo Blueprint tên là 'admin', với tiền tố URL là '/admin'
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Decorator kiểm tra quyền Admin ---
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403) # Lỗi Forbidden Access
        return f(*args, **kwargs)
    return decorated_function
# --- Kết thúc decorator ---


# Route cơ bản cho trang dashboard admin
# <<< SỬA LẠI HÀM INDEX NÀY >>>
@admin_bp.route('/')
@login_required
@admin_required
def index():
    # Truy vấn dữ liệu thống kê
    user_count = User.query.count()
    lecturer_count = User.query.filter_by(role='lecturer').count()
    student_count = User.query.filter_by(role='student').count()
    post_count = Post.query.count()
    pending_idea_count = StudentIdea.query.filter_by(status='pending').count()

    # Truyền dữ liệu thống kê vào template
    return render_template('admin/admin_dashboard.html',
                           title="Admin Dashboard",
                           user_count=user_count,
                           lecturer_count=lecturer_count,
                           student_count=student_count,
                           post_count=post_count,
                           pending_idea_count=pending_idea_count)
# <<< KẾT THÚC SỬA HÀM INDEX >>>

# --- SỬA LẠI TOÀN BỘ HÀM NÀY ---
# --- HÀM list_users ĐÃ SỬA LỖI ---
@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', None, type=str)
    active_tab = request.args.get('role_tab', 'student', type=str)
    PER_PAGE = 20

    # 1. Lọc cơ sở theo Tab
    if active_tab == 'student':
        query = User.query.filter_by(role='student')
        list_title = "Danh sách Sinh viên"
    else: # Tab 'staff'
        query = User.query.filter(User.role != 'student')
        list_title = "Danh sách Giảng viên & Admin"
        active_tab = 'staff' # Chuẩn hóa

    # 2. Áp dụng lọc tìm kiếm (nếu có)
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                User.student_id.ilike(search_term) # Tìm cả MSSV
            )
        )

    # 3. Áp dụng sắp xếp (Ví dụ: theo tên A-Z)
    # (Bạn có thể thêm logic để nhận tham số 'sort' từ request.args nếu muốn đa dạng sắp xếp)
    query = query.order_by(User.full_name.asc())

    # 4. Phân trang kết quả cuối cùng (DÙNG BIẾN query ĐÃ LỌC/SẮP XẾP)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Render template
    return render_template('admin/users_list.html',
                           title="Quản lý Người dùng",
                           users_pagination=pagination, # Truyền đúng biến pagination
                           search_query=search_query,
                           active_tab=active_tab,
                           list_title=list_title)
# --- KẾT THÚC HÀM list_users ---

# --- THÊM ROUTE MỚI ĐỂ TẠO USER ---
@admin_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required # Chỉ admin mới được tạo user
def create_user():
    form = AdminUserCreateForm()
    if form.validate_on_submit(): # Xử lý khi form hợp lệ được gửi đi (POST)
        # Hash mật khẩu
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        # Tạo đối tượng User mới
        new_user = User(full_name=form.full_name.data,
                        email=form.email.data,
                        password_hash=hashed_password,
                        role=form.role.data)
        # Nếu bạn có thêm trường student_id, class_name vào form thì gán ở đây:
        # if form.role.data == 'student':
        #    new_user.student_id = form.student_id.data
        #    new_user.class_name = form.class_name.data
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'Đã tạo người dùng "{new_user.full_name}" thành công!', 'success')
            # Chuyển hướng về trang danh sách người dùng
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi tạo người dùng: {e}', 'danger')

    # Hiển thị form cho GET request hoặc khi POST có lỗi validation
    return render_template('admin/create_user.html', title='Tạo Người dùng Mới', form=form)
# --- KẾT THÚC ROUTE CREATE USER ---



# --- THÊM ROUTE ĐỂ SỬA USER ---
@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    # Truyền user gốc vào Form để validator hoạt động đúng
    form = AdminUserUpdateForm(original_user=user_to_edit)

    if form.validate_on_submit(): # Xử lý POST
        # Cập nhật thông tin từ form
        user_to_edit.full_name = form.full_name.data
        user_to_edit.email = form.email.data
        user_to_edit.role = form.role.data
        # Cập nhật student_id và class_name (nếu có và hợp lệ)
        # Có thể thêm kiểm tra nếu role là student thì mới cập nhật?
        user_to_edit.student_id = form.student_id.data if form.student_id.data else None
        user_to_edit.class_name = form.class_name.data if form.class_name.data else None

        try:
            db.session.commit()
            flash(f'Đã cập nhật thông tin cho người dùng "{user_to_edit.full_name}"!', 'success')
            return redirect(url_for('admin.list_users')) # Quay lại danh sách user
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật người dùng: {e}', 'danger')

    elif request.method == 'GET': # Xử lý GET
        # Điền dữ liệu hiện tại vào form
        form.full_name.data = user_to_edit.full_name
        form.email.data = user_to_edit.email
        form.role.data = user_to_edit.role
        form.student_id.data = user_to_edit.student_id
        form.class_name.data = user_to_edit.class_name

    return render_template('admin/edit_user.html', title=f"Sửa Người dùng",
                           form=form, user_to_edit=user_to_edit) # Truyền user vào để hiển thị tên trên tiêu đề chẳng hạn
# --- KẾT THÚC ROUTE EDIT USER ---




# --- THÊM ROUTE LIỆT KÊ BÀI ĐĂNG/ĐỀ TÀI ---
@admin_bp.route('/posts')
@login_required
@admin_required
def list_posts():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 20 # Số bài đăng mỗi trang

    # Truy vấn tất cả bài đăng, join với User để lấy tên tác giả
    # Sắp xếp theo ngày mới nhất, phân trang
    pagination = Post.query.join(User, Post.user_id == User.id)\
                           .order_by(Post.date_posted.desc())\
                           .paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Render template mới, truyền đối tượng pagination
    return render_template('admin/posts_list.html', title="Quản lý Bài đăng & Đề tài",
                           posts_pagination=pagination)
# --- KẾT THÚC ROUTE LIST POSTS ---



# --- THÊM ROUTE ADMIN XÓA BÀI ĐĂNG ---
@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required # Chỉ Admin mới được xóa bất kỳ bài nào
def delete_post_by_admin(post_id):
    post_to_delete = Post.query.get_or_404(post_id)

    # Lấy danh sách tên file đính kèm cần xóa
    filenames_to_delete = [att.saved_filename for att in post_to_delete.attachments]

    try:
        # Xóa post (cascade sẽ xóa Attachment records trong DB)
        db.session.delete(post_to_delete)
        db.session.commit()

        # Xóa file vật lý sau khi commit DB thành công
        for filename in filenames_to_delete:
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    try: os.remove(file_path)
                    except Exception as e: print(f"Admin Delete: Error deleting file {file_path}: {e}")

        flash(f'Đã xóa bài đăng "{post_to_delete.title}"!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Đã xảy ra lỗi khi xóa bài đăng: {e}', 'danger')

    # Chuyển hướng về trang danh sách bài đăng của Admin
    return redirect(url_for('admin.list_posts'))
# --- KẾT THÚC ROUTE ADMIN XÓA BÀI ĐĂNG ---



# --- THÊM ROUTE XEM CHI TIẾT USER CHO ADMIN ---
@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def view_user_detail(user_id):
    user = User.query.get_or_404(user_id) # Lấy user theo ID

    # Tính toán Khóa học (tương tự trang /account)
    cohort = None
    if user.role == 'student' and user.student_id and len(user.student_id) >= 2:
        try:
             cohort_year = user.student_id[:2]
             cohort = f"K{cohort_year}"
        except:
             cohort = "N/A"

    # Lấy URL ảnh đại diện (tương tự trang /account)
    image_file = url_for('static', filename='profile_pics/' + user.image_file)

    # Render template mới, truyền các thông tin cần thiết
    return render_template('admin/view_user_detail.html',
                           title=f"Chi tiết: {user.full_name}",
                           user=user, # Truyền cả đối tượng user
                           cohort=cohort,
                           image_file=image_file)