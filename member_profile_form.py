from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField, TextAreaField
from wtforms import validators
from wtforms.fields.html5 import EmailField, DateField, TelField
from flask_wtf.file import FileAllowed, FileField
import app
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from wtforms.fields.html5 import TimeField
from datetime import datetime, timedelta


photos = UploadSet('photos', IMAGES)


class MemberProfileForm(FlaskForm):
    first_name = StringField(label='First Name *', validators=[
        validators.DataRequired(),
        validators.regexp('^\w+$', message='Letters only')
    ])
    last_name = StringField(label='Last Name *', validators=[
        validators.DataRequired(),
        validators.regexp('^\w+$', message='Letters only')
    ])
    email = EmailField('Email address *', validators=[validators.DataRequired(), validators.Email()])

    dob = DateField(label='Date of Birth *', validators=[
        validators.DataRequired(),
    ])    
    gender = SelectField(label='Gender', choices=['Female', 'Male', 'Other'])
    address = StringField(label='Mailing Address')
    phone = TelField(label='Phone Number *', validators=[
        validators.DataRequired(),
        
    ])
    emergency_name = StringField(label='Emergency Contact Name *', validators=[
        validators.DataRequired(),
    ])
    emergency_phone = TelField(label='Emergency Contact Phone Number *', validators=[
        validators.DataRequired(),
    ])

    subscription_type = SelectField(label='Subscription Type *', validators=[
        validators.DataRequired(),
    ], choices=['Weekly', 'Monthly', 'Yearly'])

    submit = SubmitField(label=('Submit'))

    def validate_phone(self, phone):
        phone_number = phone.data
        try:
            if not phone_number.isdigit():
                raise ValueError()  
        except:
            raise validators.ValidationError('Invalid phone number!')

    def validate_emergency_phone(self, emergency_phone):
      
        emergency_phone = emergency_phone.data
        try:
            if not emergency_phone.isdigit():
                raise ValueError()  
        except:
            raise validators.ValidationError('Invalid emergency phone number!')

    def validate_dob(self, dob):
        dob = dob.data
        today = datetime.today().strftime('%Y')
        this_month = datetime.today().strftime('%m%d')
        sixteen = int(today) - 16
        sixteen_years = str(sixteen) + this_month
        sixteen_years = datetime.strptime(sixteen_years, '%Y%m%d')
        if dob > sixteen_years.date():
            raise validators.ValidationError('You must be at least 16 to register')

class MemberRegistrationForm(MemberProfileForm):
    email = EmailField('Email address *', validators=[validators.DataRequired(), validators.Email()])
    password = PasswordField(label='Password *', validators=[
    validators.DataRequired(),
    ])

    confirm_password = PasswordField(label='Confirm Password *', validators=[
        validators.DataRequired(),
        validators.EqualTo('password', message='The two passwords you have entered do not match.')
    ])

    def validate_email(self, email):
        email = email.data
        cur = app.getCursor()
        cur.execute(f"select count(email) from login where email='{email}';")
        email_count = cur.fetchone()
        if email_count[0] != 0:
            raise validators.ValidationError('This email is already in use')

class TrainerProfileForm(MemberProfileForm):
    image = FileField(label='Trainer Photo--must be less than one GB!', 
                      validators=[FileAllowed(photos, 'Image only!')])

    specialties = StringField(label='Specialties')

    password = False
    confirm_password = False
    subscription_type = False

class TrainerScheduleForm(FlaskForm):
    session_date = DateField(label='Session date *', validators=[
        validators.DataRequired(),
    ]) 
    session_time = TimeField(label='Session time *', validators=[
        validators.DataRequired(),
    ])
    submit = SubmitField(label=('Submit'))

    def validate_session_date(self, session_date):
        session_date = session_date.data
        today = datetime.today().date()
        if session_date < today:
            raise validators.ValidationError('This date has aready passed!')
    
    def validate_session_time(self, session_time):
        session_date = self.session_date.data
        session_time = session_time.data
        today = datetime.today().date()
        now = datetime.now().time()
        if session_date == today and session_time < now:
            raise validators.ValidationError('You cannot complete this booking as this time has already passed.')

