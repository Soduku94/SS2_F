# forms.py
from flask_wtf import FlaskForm
# Import các trường liên quan đến file từ flask_wtf.file
from flask_wtf.file import (FileField,
                            FileAllowed,
                            MultipleFileField)

from wtforms import (StringField,
                     PasswordField,
                     SubmitField, BooleanField,
                     TextAreaField, SelectField, DateField)

from wtforms.validators import (DataRequired,
                                Length, Email, EqualTo,
                                ValidationError, Optional)
from flask_login import current_user
# <<< THÊM SelectMultipleField VÀO IMPORT WTFORMS >>>
from wtforms import (StringField, TextAreaField, SubmitField,
                     SelectField, MultipleFileField, SelectMultipleField)
from wtforms.validators import DataRequired, Length, ValidationError, Optional, Email # Giữ các validators cần thiết


try:
    from models import User
except ImportError:
    raise ImportError("Cannot import User model in forms.py.")

# Import model User (giữ nguyên try...except)
try:
    from models import User
except ImportError:
    raise ImportError("Không thể import model User. Kiểm tra cấu trúc file models.py và app.py.")





class LoginForm(FlaskForm):
    """Form dùng cho người dùng đăng nhập."""
    email = StringField('Email',
                        validators=[DataRequired(message="Vui lòng nhập email."),
                                    Email(message="Email không hợp lệ.")])
    password = PasswordField('Mật khẩu',
                             validators=[DataRequired(message="Vui lòng nhập mật khẩu.")])
    remember = BooleanField('Ghi nhớ đăng nhập') # Đảm bảo đã bỏ comment ở login_user nếu dùng
    submit = SubmitField('Đăng nhập')


# forms.py
# Đảm bảo import đủ:
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, Regexp
from models import User

# ... các form khác ...

# --- THAY THẾ HOÀN TOÀN CLASS NÀY ---
class RegistrationForm(FlaskForm):
    """Form chỉ dùng cho sinh viên tự đăng ký."""
    # Thứ tự: 1
    full_name = StringField('Họ và tên đầy đủ',
                            validators=[DataRequired(message="Vui lòng nhập họ tên.")])
    # Thứ tự: 2
    student_id = StringField('Mã số sinh viên',
                             validators=[DataRequired(message="Vui lòng nhập MSSV."),
                                         Length(min=7, max=10, message="MSSV phải từ 7 đến 10 ký tự."),
                                         # Optional: Thêm Regexp nếu muốn chỉ nhập số
                                         # Regexp('^[0-9]*$', message='MSSV chỉ được chứa chữ số.')
                                         ])
    # Thứ tự: 3
    email = StringField('Địa chỉ Email (dùng để đăng nhập)',
                        validators=[DataRequired(message="Vui lòng nhập email."),
                                    Email(message="Email không hợp lệ.")])
    # Thứ tự: 4
    class_name = StringField('Lớp học',
                             validators=[DataRequired(message="Vui lòng nhập lớp học."), Length(max=50)])
    # Thứ tự: 5
    date_of_birth = DateField('Ngày sinh',
                              validators=[DataRequired(message="Vui lòng nhập ngày sinh.")])
                              # Lưu ý: DateField yêu cầu định dạng YYYY-MM-DD khi nhập hoặc dùng widget
    # Thứ tự: 6
    gender = SelectField('Giới tính', choices=[
                                        ('', '--- Chọn giới tính ---'),
                                        ('male', 'Nam'),
                                        ('female', 'Nữ')
                                        # Chỉ 2 lựa chọn theo yêu cầu
                                     ], validators=[DataRequired(message="Vui lòng chọn giới tính.")])
    # Thứ tự: 7
    phone_number = StringField('Số điện thoại',
                               validators=[DataRequired(message="Vui lòng nhập số điện thoại."),
                                           Length(min=9, max=15, message="Số điện thoại không hợp lệ.")])
                                           # Optional: Thêm Regexp kiểm tra định dạng SĐT Việt Nam
    # Thứ tự: 8
    password = PasswordField('Mật khẩu',
                             validators=[DataRequired(message="Vui lòng nhập mật khẩu."),
                                         Length(min=6, message="Mật khẩu cần ít nhất 6 ký tự.")])
    # Thứ tự: 9
    confirm_password = PasswordField('Xác nhận mật khẩu',
                                     validators=[DataRequired(message="Vui lòng xác nhận mật khẩu."),
                                                 EqualTo('password', message='Mật khẩu xác nhận không khớp.')])
    submit = SubmitField('Đăng ký tài khoản')

    # Validator kiểm tra trùng lặp MSSV (giữ nguyên)
    def validate_student_id(self, student_id):
        user = User.query.filter_by(student_id=student_id.data).first()
        if user:
            raise ValidationError('MSSV này đã tồn tại.')

    # Validator kiểm tra trùng lặp Email (giữ nguyên)
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email này đã được sử dụng.')



class PostForm(FlaskForm):
    """Form dùng cho Giảng viên tạo Bài đăng/Đề tài mới."""
    title = StringField('Tiêu đề',
                        validators=[DataRequired(message="Vui lòng nhập tiêu đề.")])
    content = TextAreaField('Nội dung',
                            validators=[DataRequired(message="Vui lòng nhập nội dung.")])
    post_type = SelectField('Loại bài đăng',
                            choices=[('article', 'Bài viết / Thông báo'), ('topic', 'Đề tài Nghiên cứu')],
                            validators=[DataRequired(message="Vui lòng chọn loại bài đăng.")])
    # <<< THÊM LẠI TRƯỜNG ATTACHMENT >>>
    # Đổi tên thành 'attachments' (số nhiều)
    attachments = MultipleFileField('Tệp đính kèm (Có thể chọn nhiều file)',
                                    validators=[FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx','pptx'],
                                                            'Chỉ chấp nhận PDF, Word, Excel và PowerPoint!')])
    # <<< THÊM LẠI TRƯỜNG STATUS >>>
    status = SelectField('Trạng thái Đề tài',
                         choices=[('pending', 'Chờ duyệt/Tìm SV (Pending)'),
                                  ('working_on', 'Đang thực hiện (Working On)'),
                                  ('closed', 'Đã đóng (Closed)')],
                         default='pending') # Mặc định là pending
    is_featured = BooleanField('Ghim / Đặt làm nổi bật')
    submit = SubmitField('Đăng bài')


class UpdateAccountForm(FlaskForm):
    # <<< THÊM CÁC TRƯỜNG MỚI >>>
    date_of_birth = DateField('Ngày sinh', validators=[Optional()])
    gender = SelectField('Giới tính', choices=[
                                        ('', '--- Chọn giới tính ---'), # Lựa chọn trống
                                        ('male', 'Nam'),
                                        ('female', 'Nữ'),



                                     ], validators=[Optional()])
    picture = FileField('Cập nhật Ảnh đại diện (jpg, png, jpeg, gif)',
                        validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Chỉ chấp nhận file ảnh!')])
    phone_number = StringField('Số điện thoại', validators=[Optional(), Length(min=9, max=15)]) # Optional, giới hạn độ dài
    contact_email = StringField('Email Liên hệ (khác)', validators=[Optional(), Email(message="Email liên hệ không hợp lệ.")]) # Optional, kiểm tra định dạng
    about_me = TextAreaField('Giới thiệu bản thân', validators=[Optional(), Length(max=500)]) # Optional, giới hạn 500 ký tự
    class_name = StringField('Lớp', validators=[Optional(), Length(max=50)])
    # <<< KẾT THÚC THÊM TRƯỜNG >>>

    def validate_contact_email(self, contact_email):
        # ... (logic kiểm tra contact_email như trước) ...
        if contact_email.data and contact_email.data != current_user.contact_email:
            if contact_email.data == current_user.email:
                raise ValidationError('Email liên hệ không được trùng với email đăng nhập.')
            user_by_contact = User.query.filter_by(contact_email=contact_email.data).first()
            user_by_main = User.query.filter_by(email=contact_email.data).first()
            if user_by_contact or user_by_main:
                raise ValidationError('Email liên hệ này đã được sử dụng.')

    # def validate_phone_number(self, phone_number):
    #     # ... (logic kiểm tra phone_number như trước) ...
    #     if phone_number.data and phone_number.data != current_user.phone_number:
    #         user = User.query.filter_by(phone_number=phone_number.data).first()
    #         if user:
    #             raise ValidationError('Số điện thoại này đã được sử dụng.')

    submit = SubmitField('Cập nhật thông tin')


class ChangePasswordForm(FlaskForm):
    """Form cho người dùng thay đổi mật khẩu."""
    current_password = PasswordField('Mật khẩu hiện tại',
                                     validators=[DataRequired(message="Vui lòng nhập mật khẩu hiện tại.")])
    new_password = PasswordField('Mật khẩu mới',
                                 validators=[DataRequired(message="Vui lòng nhập mật khẩu mới."),
                                             Length(min=6, message="Mật khẩu mới cần ít nhất 6 ký tự.")])
    confirm_new_password = PasswordField('Xác nhận mật khẩu mới',
                                         validators=[DataRequired(message="Vui lòng xác nhận mật khẩu mới."),
                                                     EqualTo('new_password', message='Mật khẩu mới không khớp.')])
    submit = SubmitField('Đổi mật khẩu')

    # Custom validator để kiểm tra mật khẩu hiện tại có đúng không
    def validate_current_password(self, current_password):
        if not current_user.check_password(current_password.data):
            raise ValidationError('Mật khẩu hiện tại không đúng.')
# --- KẾT THÚC THÊM CLASS ---


# --- THÊM FORM MỚI CHO GỬI Ý TƯỞNG ---
class IdeaSubmissionForm(FlaskForm):
    """Form cho Sinh viên gửi ý tưởng mới."""
    title = StringField('Tiêu đề Ý tưởng',
                        validators=[DataRequired(message="Vui lòng nhập tiêu đề."), Length(max=150)])
    description = TextAreaField('Mô tả chi tiết Ý tưởng',
                                validators=[DataRequired(message="Vui lòng mô tả ý tưởng của bạn.")])

    # <<< THÊM TRƯỜNG CHỌN NGƯỜI NHẬN >>>
    # coerce=int để đảm bảo giá trị submit là list các số nguyên (User IDs)
    recipients = SelectMultipleField('Gửi đến Giảng viên (Chọn một hoặc nhiều)', coerce=int, validators=[Optional()])
    # choices sẽ được thêm vào từ route
    # <<< KẾT THÚC THÊM >>>


    # <<< THÊM TRƯỜNG NÀY >>>
    attachments = MultipleFileField('Tệp đính kèm (Tùy chọn)',
                                    validators=[
                                        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'pptx', 'png', 'jpg', 'jpeg'],
                                                    'Chỉ chấp nhận tệp văn bản, bảng tính, trình chiếu hoặc ảnh!')])
    submit = SubmitField('Gửi Ý tưởng')
# --- KẾT THÚC THÊM FORM ---



# --- THÊM FORM MỚI CHO REVIEW Ý TƯỞNG ---
class IdeaReviewForm(FlaskForm):
    """Form cho Giảng viên phản hồi và cập nhật trạng thái ý tưởng."""
    feedback = TextAreaField('Nội dung Phản hồi', validators=[Optional()]) # Phản hồi có thể có hoặc không
    status = SelectField('Cập nhật Trạng thái',
                         choices=[
                             # Giữ lại các trạng thái có thể có
                             ('pending', 'Đang chờ duyệt'),
                             ('reviewed', 'Đã xem xét (Reviewed)'), # Thêm trạng thái này?
                             ('approved', 'Chấp thuận (Approved)'),
                             ('rejected', 'Từ chối (Rejected)')
                         ],
                         validators=[DataRequired(message="Vui lòng chọn trạng thái.")]) # Bắt buộc chọn trạng thái
    submit = SubmitField('Lưu Phản hồi & Trạng thái')
# --- KẾT THÚC THÊM FORM ---


# === THÊM CLASS FORM MỚI CHO ADMIN TẠO USER ===
class AdminUserCreateForm(FlaskForm):
    """Form cho Admin tạo người dùng mới (GV hoặc SV)."""
    full_name = StringField('Họ và tên đầy đủ',
                            validators=[DataRequired(message="Vui lòng nhập họ tên.")])
    email = StringField('Email (Dùng để đăng nhập)',
                        validators=[DataRequired(message="Vui lòng nhập email."),
                                    Email(message="Email không hợp lệ.")])
    password = PasswordField('Mật khẩu',
                             validators=[DataRequired(message="Vui lòng nhập mật khẩu."),
                                         Length(min=6, message="Mật khẩu cần ít nhất 6 ký tự.")])
    confirm_password = PasswordField('Xác nhận mật khẩu',
                                     validators=[DataRequired(message="Vui lòng xác nhận mật khẩu."),
                                                 EqualTo('password', message='Mật khẩu xác nhận không khớp.')])
    role = SelectField('Vai trò', choices=[
                                        ('lecturer', 'Giảng viên'),
                                        ('student', 'Sinh viên'),
                                        ('admin', 'Admin')
                                     ], validators=[DataRequired(message="Vui lòng chọn vai trò.")])
    # Có thể thêm các trường student_id, class_name ở đây nếu muốn Admin nhập luôn khi tạo SV
    # student_id = StringField('Mã số sinh viên (Nếu là SV)', validators=[Optional(), Length(...)])
    # class_name = StringField('Lớp (Nếu là SV)', validators=[Optional(), Length(...)])

    submit = SubmitField('Tạo người dùng')

    # Vẫn cần kiểm tra email duy nhất
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email này đã tồn tại. Vui lòng chọn email khác.')



# --- THÊM CLASS FORM MỚI CHO ADMIN SỬA USER ---
class AdminUserUpdateForm(FlaskForm):
    """Form cho Admin cập nhật thông tin người dùng."""
    # Các trường có thể sửa
    full_name = StringField('Họ và tên đầy đủ',
                            validators=[DataRequired(message="Vui lòng nhập họ tên.")])
    email = StringField('Email (Dùng để đăng nhập)',
                        validators=[DataRequired(message="Vui lòng nhập email."),
                                    Email(message="Email không hợp lệ.")])
    role = SelectField('Vai trò', choices=[
                                        ('lecturer', 'Giảng viên'),
                                        ('student', 'Sinh viên'),
                                        ('admin', 'Admin') # Cho phép đổi thành Admin? (Cẩn thận)
                                     ], validators=[DataRequired(message="Vui lòng chọn vai trò.")])
    # Các trường thông tin thêm (tùy chọn)
    student_id = StringField('Mã số sinh viên',
                              validators=[Optional(), Length(min=7, max=10, message="MSSV không hợp lệ (nếu có).")])
    class_name = StringField('Lớp', validators=[Optional(), Length(max=50)])

    submit = SubmitField('Lưu thay đổi')

    # --- Validator tùy chỉnh ---
    # Cần truyền user gốc vào form để validator hoạt động đúng
    def __init__(self, original_user, *args, **kwargs):
        super(AdminUserUpdateForm, self).__init__(*args, **kwargs)
        self.original_user = original_user # Lưu user gốc

    # Kiểm tra email mới có trùng với người khác (TRỪ user hiện tại) không
    def validate_email(self, email):
        if email.data != self.original_user.email: # Chỉ kiểm tra nếu email bị thay đổi
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Email này đã được sử dụng bởi một tài khoản khác.')

    # Kiểm tra MSSV mới có trùng với người khác (TRỪ user hiện tại) không
    def validate_student_id(self, student_id):
         # Chỉ kiểm tra nếu có nhập MSSV VÀ nó khác với MSSV gốc (nếu có)
        if student_id.data and student_id.data != self.original_user.student_id:
            user = User.query.filter_by(student_id=student_id.data).first()
            if user:
                raise ValidationError('MSSV này đã được sử dụng bởi một tài khoản khác.')

# --- KẾT THÚC FORM UPDATE ---