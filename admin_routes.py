import os
import uuid
import secrets
from functools import wraps

from flask import (Blueprint, request, render_template, abort, flash, redirect, url_for,
                   current_app)

from flask_login import login_required, current_user

from sqlalchemy import or_, asc, desc

from werkzeug.utils import secure_filename

from app import app

try:
    from PIL import Image
except ImportError:
    Image = None

from extensions import db, bcrypt

from models import User, Post, StudentIdea, Attachment, IdeaAttachment, AcademicWork

from forms import (AdminUserCreateForm, AdminUserUpdateForm, IdeaReviewForm,
                   AcademicWorkForm)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def save_showcase_image(form_picture, old_picture_filename=None):
    if not Image:
        flash("Thư viện xử lý ảnh (Pillow) chưa được cài đặt.", "warning")
        return None
    if not form_picture:
        return None

    showcase_pics_dir = current_app.config.get('ACADEMIC_WORK_IMAGE_FOLDER')
    if not showcase_pics_dir:
        showcase_pics_dir = os.path.join(current_app.root_path, 'static', 'academic_work_images')
        os.makedirs(showcase_pics_dir, exist_ok=True)
        print("WARNING: ACADEMIC_WORK_IMAGE_FOLDER not set in config, using default static/academic_work_images/")

    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(showcase_pics_dir, picture_fn)

    if old_picture_filename:
        try:
            old_picture_path = os.path.join(showcase_pics_dir, old_picture_filename)
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)
        except Exception as e:
            print(f"Lỗi khi xóa ảnh showcase cũ {old_picture_path}: {e}")

    output_width = 800
    try:
        img = Image.open(form_picture)
        if img.width > output_width:
            aspect_ratio = img.height / img.width
            output_height = int(output_width * aspect_ratio)
            img.thumbnail((output_width, output_height))
        img.save(picture_path)
        return picture_fn
    except Exception as e:
        print(f"Lỗi khi lưu hoặc resize ảnh showcase: {e}")
        flash("Đã xảy ra lỗi khi xử lý ảnh.", "danger")
        return None

@admin_bp.route('/')
@login_required
@admin_required
def index():
    user_count = User.query.count()
    lecturer_count = User.query.filter_by(role='lecturer').count()
    student_count = User.query.filter_by(role='student').count()
    post_count = Post.query.count()
    pending_idea_count = StudentIdea.query.filter_by(status='pending').count()
    return render_template('admin/admin_dashboard.html',
                           title="Admin Dashboard",
                           user_count=user_count,
                           lecturer_count=lecturer_count,
                           student_count=student_count,
                           post_count=post_count,
                           pending_idea_count=pending_idea_count)

@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', None, type=str)
    active_tab = request.args.get('role_tab', 'student', type=str)
    PER_PAGE = 20
    if active_tab == 'student':
        query = User.query.filter_by(role='student')
        list_title = "Danh sách sinh viên"
    else:
        query = User.query.filter(User.role != 'student')
        list_title = "Danh sách giảng viên & admin"
        active_tab = 'staff'
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(or_(User.full_name.ilike(search_term), User.email.ilike(search_term), User.student_id.ilike(search_term)))
    query = query.order_by(User.full_name.asc())
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('admin/users_list.html',
                           title="Quản lý người dùng",
                           users_pagination=pagination,
                           search_query=search_query,
                           active_tab=active_tab,
                           list_title=list_title)

@admin_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = AdminUserCreateForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(full_name=form.full_name.data,
                        email=form.email.data,
                        password_hash=hashed_password,
                        role=form.role.data)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'Đã tạo người dùng "{new_user.full_name}" thành công!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi tạo người dùng: {e}', 'danger')
    return render_template('admin/create_user.html', legend=' Tạo người dùng mới ', form=form)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    form = AdminUserUpdateForm(original_user=user_to_edit)
    if form.validate_on_submit():
        user_to_edit.full_name = form.full_name.data
        user_to_edit.email = form.email.data
        user_to_edit.role = form.role.data
        user_to_edit.student_id = form.student_id.data if form.student_id.data else None
        user_to_edit.class_name = form.class_name.data if form.class_name.data else None
        try:
            db.session.commit()
            flash(f'Đã cập nhật thông tin cho người dùng "{user_to_edit.full_name}"!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật người dùng: {e}', 'danger')
    elif request.method == 'GET':
        form.full_name.data = user_to_edit.full_name
        form.email.data = user_to_edit.email
        form.role.data = user_to_edit.role
        form.student_id.data = user_to_edit.student_id
        form.class_name.data = user_to_edit.class_name
    return render_template('admin/edit_user.html', title=f"Sửa Người dùng", form=form, user_to_edit=user_to_edit)

@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def view_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    cohort = None
    if user.role == 'student' and user.student_id and len(user.student_id) >= 2:
        try: cohort = f"K{user.student_id[:2]}"
        except: cohort = "N/A"
    image_folder = 'user_pics' if user.image_file and not user.image_file.startswith('default') else 'tech_background_right.jpg'
    image_file_name = user.image_file or 'default.jpg'
    if image_folder == 'tech_background_right.jpg':
        if user.gender == 'female': image_file_name = 'default_female.jpg'
        elif user.gender == 'male': image_file_name = 'default_male.jpg'
        else: image_file_name = 'default.jpg'
    image_url = url_for('static', filename=f'{image_folder}/{image_file_name}')

    return render_template('admin/view_user_detail.html',
                           title=f"Chi tiết: {user.full_name}",
                           user=user,
                           cohort=cohort,
                           image_file=image_url)

@admin_bp.route('/posts')
@login_required
@admin_required
def list_posts():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 20
    pagination = Post.query.join(User, Post.user_id == User.id)\
                           .order_by(Post.date_posted.desc())\
                           .paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('admin/posts_list.html', title="Manage posts and topics", posts_pagination=pagination)

@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post_by_admin(post_id):
     post_to_delete = Post.query.get_or_404(post_id)
     filenames_to_delete = [att.saved_filename for att in post_to_delete.attachments]
     try:
         db.session.delete(post_to_delete)
         db.session.commit()
         for filename in filenames_to_delete:
             if filename:
                 file_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), filename)
                 if os.path.exists(file_path):
                     try: os.remove(file_path)
                     except Exception as e: print(f"Admin Delete: Error deleting file {file_path}: {e}")
         flash(f'Đã xóa bài đăng "{post_to_delete.title}"!', 'success')
     except Exception as e:
         db.session.rollback()
         flash(f'Đã xảy ra lỗi khi xóa bài đăng: {e}', 'danger')
     return redirect(url_for('admin.list_posts'))

@admin_bp.route('/academic-works')
@login_required
@admin_required
def list_academic_works():
    try:
        year_from_str = request.args.get('year_from', None)
        year_to_str = request.args.get('year_to', None)
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('q', None, type=str)
        filter_type = request.args.get('item_type', None, type=str)
        filter_published = request.args.get('published', None, type=str)
        filter_featured = request.args.get('featured', None, type=str)

        PER_PAGE = 15
        query = AcademicWork.query

        year_from = None
        if year_from_str and year_from_str.isdigit():
            year_from = int(year_from_str)

        year_to = None
        if year_to_str and year_to_str.isdigit():
            year_to = int(year_to_str)

        if year_from is not None and year_to is not None:
            if year_from <= year_to:
                query = query.filter(AcademicWork.year.between(year_from, year_to))
        elif year_from is not None:
            query = query.filter(AcademicWork.year >= year_from)
        elif year_to is not None:
            query = query.filter(AcademicWork.year <= year_to)

        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                AcademicWork.title.ilike(search_term),
                AcademicWork.authors_text.ilike(search_term),
                AcademicWork.abstract.ilike(search_term)
            ))

        if filter_type: query = query.filter(AcademicWork.item_type == filter_type)

        if filter_published == 'true':
            query = query.filter(AcademicWork.is_published == True)
        elif filter_published == 'false':
            query = query.filter(AcademicWork.is_published == False)

        if filter_featured == 'true':
            query = query.filter(AcademicWork.is_featured == True)
        elif filter_featured == 'false':
            query = query.filter(AcademicWork.is_featured == False)

        query = query.order_by(AcademicWork.year.desc().nullslast(), AcademicWork.date_added.desc())
        pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

        distinct_types_results = db.session.query(AcademicWork.item_type).distinct().order_by(
            AcademicWork.item_type).all()
        distinct_years_results = db.session.query(AcademicWork.year).filter(
            AcademicWork.year != None).distinct().order_by(AcademicWork.year.desc()).all()

        distinct_types = [t[0] for t in distinct_types_results]
        distinct_years = [y[0] for y in distinct_years_results]

        return render_template('admin/academic_works_list.html',
                               title="Feature Works Manager",
                               items_pagination=pagination,
                               search_query=search_query,
                               distinct_types=distinct_types,
                               distinct_years=distinct_years,
                               filter_type=filter_type,
                               filter_year_from=year_from_str,
                               filter_year_to=year_to_str,
                               filter_published=filter_published,
                               filter_featured=filter_featured)

    except Exception as e:
        app.logger.error(f"An error occurred in list_academic_works: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again later.", "danger")
        return redirect(url_for('admin.index'))

@admin_bp.route('/academic-works/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_academic_work():
    form = AcademicWorkForm()
    if form.validate_on_submit():
        new_item = AcademicWork(
            title=form.title.data, item_type=form.item_type.data,
            authors_text=form.authors_text.data, year=form.year.data,
            abstract=form.abstract.data, full_content=form.full_content.data,
            external_link=form.external_link.data, is_published=form.is_published.data,
            is_featured=form.is_featured.data,
            user_id=current_user.id
        )
        image_filename = None
        if form.image_file.data:
            try:
                image_filename = save_showcase_image(form.image_file.data)
                if image_filename: new_item.image_file = image_filename
            except Exception as img_e: flash(f"Lỗi xử lý ảnh: {img_e}", "danger")

        try:
            db.session.add(new_item)
            db.session.commit()
            flash(f'Đã tạo công trình "{new_item.title}" thành công!', 'success')
            return redirect(url_for('admin.list_academic_works'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi lưu công trình: {e}', 'danger')
            if image_filename:
                try:
                    img_path = os.path.join(current_app.config.get('ACADEMIC_WORK_IMAGE_FOLDER','static/academic_work_images'), image_filename)
                    if os.path.exists(img_path): os.remove(img_path)
                except Exception as del_e: print(f"Lỗi khi xóa ảnh showcase (sau lỗi commit): {del_e}")

    return render_template('admin/academic_work_form.html',
                           title="New Showcase", form=form, legend="Thêm Công trình Mới")

@admin_bp.route('/academic-works/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_academic_work(item_id):
    item = AcademicWork.query.get_or_404(item_id)
    form = AcademicWorkForm(obj=item if request.method == 'GET' else None)

    if form.validate_on_submit():
        old_image = item.image_file
        new_image_filename = None
        item.title = form.title.data
        item.item_type = form.item_type.data
        item.authors_text = form.authors_text.data
        item.year = form.year.data
        item.abstract = form.abstract.data
        item.full_content = form.full_content.data
        item.external_link = form.external_link.data
        item.is_published = form.is_published.data

        item.full_content = form.full_content.data

        item.is_featured = form.is_featured.data
        # item.user_id = current_user.id

        if form.image_file.data:
            try:
                new_image_filename = save_showcase_image(form.image_file.data, old_picture_filename=old_image)
                if new_image_filename:
                    item.image_file = new_image_filename
            except Exception as img_e: flash(f"Lỗi xử lý ảnh mới: {img_e}", "danger")

        try:
            db.session.commit()
            flash(f'Đã cập nhật công trình "{item.title}"!', 'success')
            return redirect(url_for('admin.list_academic_works'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật công trình: {e}', 'danger')
            if new_image_filename:
                 try:
                    img_path = os.path.join(current_app.config.get('ACADEMIC_WORK_IMAGE_FOLDER','static/academic_work_images'), new_image_filename)
                    if os.path.exists(img_path): os.remove(img_path)
                 except Exception as del_e: print(f"Lỗi khi xóa ảnh showcase mới (sau lỗi commit): {del_e}")

    return render_template('admin/academic_work_form.html',
                           title="Sửa Công trình Showcase", form=form,
                           legend=f"Chỉnh sửa: {item.title}", item=item)

@admin_bp.route('/academic-works/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_academic_work(item_id):
    item = AcademicWork.query.get_or_404(item_id)
    image_to_delete = item.image_file

    try:
        db.session.delete(item)
        db.session.commit()
        flash(f'Đã xóa công trình "{item.title}".', 'success')

        if image_to_delete:
             try:
                img_path = os.path.join(current_app.config.get('ACADEMIC_WORK_IMAGE_FOLDER','static/academic_work_images'), image_to_delete)
                if os.path.exists(img_path):
                     os.remove(img_path)
                     print(f"Admin Deleted showcase image: {img_path}")
             except Exception as del_e:
                print(f"Lỗi khi xóa file ảnh showcase {image_to_delete}: {del_e}")

    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa công trình: {e}', 'danger')

    return redirect(url_for('admin.list_academic_works'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Bạn không thể xóa chính tài khoản của mình.', 'warning')
        return redirect(url_for('admin.list_users'))

    user_to_delete = User.query.get_or_404(user_id)

    try:
        if user_to_delete.image_file and not user_to_delete.image_file.startswith('default'):
            user_pics_dir = current_app.config.get('USER_PICS_FOLDER',
                                                   os.path.join(current_app.root_path, 'static', 'user_pics'))
            image_path = os.path.join(user_pics_dir, user_to_delete.image_file)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    app.logger.error(f"Error deleting profile picture for user {user_id} during admin delete: {e}")

        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'Người dùng "{user_to_delete.full_name}" đã được xóa thành công.', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting user {user_id} by admin: {e}")
        flash(f'Lỗi khi xóa người dùng: {e}', 'danger')

    return redirect(url_for('admin.list_users'))