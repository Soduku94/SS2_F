# forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import (StringField, PasswordField, SubmitField, BooleanField,
                     TextAreaField, SelectField, DateField, IntegerField,
                     SelectMultipleField)
from wtforms.validators import (DataRequired, Length, Email, EqualTo,
                                ValidationError, Optional, URL, Regexp, NumberRange)
from flask_login import current_user
from models import User  # Assuming User model is correctly placed and importable


class LoginForm(FlaskForm):
    """Form for user login."""
    email = StringField('Email',
                        validators=[DataRequired(message="Please enter your email."),
                                    Email(message="Invalid email address.")])
    password = PasswordField('Password',
                             validators=[DataRequired(message="Please enter your password.")])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    """Form for student self-registration."""
    full_name = StringField('Full Name',
                            validators=[DataRequired(message="Please enter your full name.")])
    student_id = StringField('Student ID',
                             validators=[DataRequired(message="Please enter your Student ID."),
                                         Length(min=7, max=10,
                                                message="Student ID must be between 7 and 10 characters."),
                                         # Optional: Add Regexp if you want numbers only
                                         # Regexp('^[0-9]*$', message='Student ID must contain only digits.')
                                         ])
    email = StringField('Email Address (for login)',
                        validators=[DataRequired(message="Please enter your email address."),
                                    Email(message="Invalid email address.")])
    class_name = StringField('Class Name',
                             validators=[DataRequired(message="Please enter your class name."), Length(max=50)])
    date_of_birth = DateField('Date of Birth',
                              validators=[DataRequired(message="Please enter your date of birth.")])
    # Note: DateField requires YYYY-MM-DD format or a datepicker widget
    gender = SelectField('Gender', choices=[
        ('', '--- Select Gender ---'),
        ('male', 'Male'),
        ('female', 'Female')
    ], validators=[DataRequired(message="Please select your gender.")])
    phone_number = StringField('Phone Number',
                               validators=[DataRequired(message="Please enter your phone number."),
                                           Length(min=9, max=15, message="Invalid phone number length.")])
    # Optional: Add Regexp for specific phone number formats
    password = PasswordField('Password',
                             validators=[DataRequired(message="Please enter a password."),
                                         Length(min=6, message="Password must be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(message="Please confirm your password."),
                                                 EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Register Account')

    def validate_student_id(self, student_id):
        user = User.query.filter_by(student_id=student_id.data).first()
        if user:
            raise ValidationError('This Student ID is already registered.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email address is already in use.')


class PostForm(FlaskForm):
    """Form for Lecturers to create or update Posts/Topics."""
    title = StringField('Title',
                        validators=[DataRequired(message="Please enter a title.")])
    content = TextAreaField('Content',
                            validators=[DataRequired(message="Please enter the content.")])
    post_type = SelectField('Post Type',
                            choices=[('article', 'Article / Announcement'), ('topic', 'Research Topic')],
                            validators=[DataRequired(message="Please select a post type.")])

    attachments = MultipleFileField('Attachments (You can select multiple files)',
                                    validators=[Optional(),
                                                FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'pptx'],
                                                            'Only PDF, Word, Excel, and PowerPoint files are allowed!')])
    tags = StringField('Tags',
                       validators=[Optional()])

    status = SelectField('Status',
                         choices=[
                             ('pending', 'Pending Approval'),
                             ('published', 'Published'),
                             ('recruiting', 'Recruiting Students'),
                             ('working_on', 'In Progress'),
                             ('closed', 'Closed/Finished')
                         ],
                         default='pending')

    is_featured = BooleanField('Pin / Mark as Featured')
    submit = SubmitField('Save Post / Topic')


class UpdateAccountForm(FlaskForm):
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField('Gender', choices=[
        ('', '--- Select Gender ---'),
        ('male', 'Male'),
        ('female', 'Female'),
    ], validators=[Optional()])
    picture = FileField('Update Profile Picture (jpg, png, jpeg, gif)',
                        validators=[Optional(),
                                    FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Only image files are allowed!')])
    phone_number = StringField('Phone Number',
                               validators=[Optional(), Length(min=9, max=15, message="Invalid phone number length.")])
    contact_email = StringField('Alternative Contact Email',
                                validators=[Optional(), Email(message="Invalid contact email address.")])
    about_me = TextAreaField('About Me',
                             validators=[Optional(), Length(max=500, message="About me cannot exceed 500 characters.")])
    class_name = StringField('Class', validators=[Optional(), Length(max=50)])
    delete_picture = BooleanField('Remove current profile picture and use default')

    def validate_contact_email(self, contact_email):
        if contact_email.data and contact_email.data.strip():  # Check if data exists and is not just whitespace
            if current_user.is_authenticated and contact_email.data == current_user.contact_email:
                return  # No change, no validation needed
            if current_user.is_authenticated and contact_email.data == current_user.email:
                raise ValidationError('Alternative contact email cannot be the same as your login email.')
            # Check if this contact email is used as a main email or contact email by another user
            user_by_contact = User.query.filter(User.id != current_user.id,
                                                User.contact_email == contact_email.data).first()
            user_by_main = User.query.filter(User.id != current_user.id, User.email == contact_email.data).first()
            if user_by_contact or user_by_main:
                raise ValidationError('This contact email is already in use.')

    # def validate_phone_number(self, phone_number):
    #     if phone_number.data and phone_number.data.strip():
    #         if current_user.is_authenticated and phone_number.data == current_user.phone_number:
    #             return
    #         user = User.query.filter(User.id != current_user.id, User.phone_number == phone_number.data).first()
    #         if user:
    #             raise ValidationError('This phone number is already in use.')

    submit = SubmitField('Update Information')


class ChangePasswordForm(FlaskForm):
    """Form for users to change their password."""
    current_password = PasswordField('Current Password',
                                     validators=[DataRequired(message="Please enter your current password.")])
    new_password = PasswordField('New Password',
                                 validators=[DataRequired(message="Please enter a new password."),
                                             Length(min=6, message="New password must be at least 6 characters long.")])
    confirm_new_password = PasswordField('Confirm New Password',
                                         validators=[DataRequired(message="Please confirm your new password."),
                                                     EqualTo('new_password', message='New passwords must match.')])
    submit = SubmitField('Change Password')

    def validate_current_password(self, current_password):
        if not current_user.check_password(current_password.data):
            raise ValidationError('Incorrect current password.')


class IdeaSubmissionForm(FlaskForm):
    """Form for Students to submit new ideas."""
    title = StringField('Idea Title',
                        validators=[DataRequired(message="Please enter a title for your idea."), Length(max=150)])
    description = TextAreaField('Detailed Description of Idea',
                                validators=[DataRequired(message="Please describe your idea.")])
    recipients = SelectMultipleField('Send to Lecturers (Select one or more)', coerce=int, validators=[Optional()])
    # choices will be added from the route

    attachments = MultipleFileField('Attachments (Optional)',
                                    validators=[Optional(),
                                                FileAllowed(
                                                    ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'pptx', 'png', 'jpg', 'jpeg'],
                                                    'Only text, spreadsheet, presentation or image files are allowed!')])
    submit = SubmitField('Submit Idea')


class IdeaReviewForm(FlaskForm):
    """Form for Lecturers to provide feedback and update idea status."""
    feedback = TextAreaField('Feedback Content', validators=[Optional()])
    status = SelectField('Update Status',
                         choices=[
                             ('pending', 'Pending Approval'),
                             ('reviewed', 'Reviewed'),
                             ('approved', 'Approved'),
                             ('rejected', 'Rejected')
                         ],
                         validators=[DataRequired(message="Please select a status.")])
    submit = SubmitField('Save Feedback & Status')


class AdminUserCreateForm(FlaskForm):
    """Form for Admin to create new users (Lecturer or Student)."""
    full_name = StringField('Full Name',
                            validators=[DataRequired(message="Please enter the full name.")])
    email = StringField('Email (Used for login)',
                        validators=[DataRequired(message="Please enter an email address."),
                                    Email(message="Invalid email address.")])
    password = PasswordField('Password',
                             validators=[DataRequired(message="Please enter a password."),
                                         Length(min=6, message="Password must be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(message="Please confirm the password."),
                                                 EqualTo('password', message='Passwords must match.')])
    role = SelectField('Role', choices=[
        ('lecturer', 'Lecturer'),
        ('student', 'Student'),
        ('admin', 'Admin')  # Be cautious when assigning Admin role
    ], validators=[DataRequired(message="Please select a role.")])
    student_id = StringField('Student ID (If Student)', validators=[Optional(), Length(min=7, max=10,
                                                                                       message="Student ID must be 7-10 characters if provided.")])
    class_name = StringField('Class (If Student)', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Create User')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email address already exists. Please choose a different one.')

    def validate_student_id(self, student_id):
        if student_id.data:  # Only validate if student_id is provided
            user = User.query.filter_by(student_id=student_id.data).first()
            if user:
                raise ValidationError('This Student ID already exists. Please choose a different one.')


class AdminUserUpdateForm(FlaskForm):
    """Form for Admin to update user information."""
    full_name = StringField('Full Name',
                            validators=[DataRequired(message="Please enter the full name.")])
    email = StringField('Email (Used for login)',
                        validators=[DataRequired(message="Please enter an email address."),
                                    Email(message="Invalid email address.")])
    role = SelectField('Role', choices=[
        ('lecturer', 'Lecturer'),
        ('student', 'Student'),
        ('admin', 'Admin')  # Be cautious when changing roles, especially to Admin
    ], validators=[DataRequired(message="Please select a role.")])
    student_id = StringField('Student ID',
                             validators=[Optional(), Length(min=7, max=10,
                                                            message="Student ID must be 7-10 characters if provided.")])
    class_name = StringField('Class', validators=[Optional(), Length(max=50)])
    # Admin might also want to update other fields like phone, DOB, gender, etc. Add them as needed.

    submit = SubmitField('Save Changes')

    def __init__(self, original_user, *args, **kwargs):
        super(AdminUserUpdateForm, self).__init__(*args, **kwargs)
        self.original_user = original_user

    def validate_email(self, email):
        if email.data != self.original_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('This email address is already in use by another account.')

    def validate_student_id(self, student_id):
        if student_id.data and student_id.data != self.original_user.student_id:
            user = User.query.filter_by(student_id=student_id.data).first()
            if user:
                raise ValidationError('This Student ID is already in use by another account.')


class AcademicWorkForm(FlaskForm):
    """Form for Admin/Dean to add or edit AcademicWork (Showcase Items)."""
    title = StringField('Work Title',
                        validators=[DataRequired(message="Please enter a title."),
                                    Length(max=200, message="Title cannot exceed 200 characters.")])

    is_featured = BooleanField('Display on Showcase Carousel (Top Section)?')

    item_type = SelectField('Type of Work',
                            choices=[
                                ('thesis', 'Thesis / Capstone Project'),
                                ('proceeding', 'Research Paper / Conference Proceeding'),
                                ('project', 'Other Research Project')
                            ],
                            validators=[DataRequired(message="Please select the type of work.")])

    authors_text = StringField('Author(s) / Team Name',
                               validators=[DataRequired(message="Please enter the author(s)/team name."),
                                           Length(max=300)])

    year = IntegerField('Year of Completion / Publication',
                        validators=[Optional(),
                                    NumberRange(min=1990, max=2100, message="Invalid year.")])

    abstract = TextAreaField('Abstract / Short Introduction',
                             validators=[Optional()])

    full_content = TextAreaField('Detailed Content',
                                 validators=[Optional()])  # Trix/CKEditor can be used for this in template

    image_file = FileField('Cover Image (Optional)',
                           validators=[Optional(),
                                       FileAllowed(['jpg', 'png', 'jpeg', 'gif'],
                                                   'Only image files (jpg, png, jpeg, gif) are allowed!')])

    external_link = StringField('External Link (PDF, Github, etc. - Optional)',
                                validators=[Optional(), URL(require_tld=True, message="Invalid URL format.")])

    is_published = BooleanField('Make this work publicly visible on the Showcase page?')
    submit = SubmitField('Save Work')