from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField
from wtforms import validators
from wtforms.fields.html5 import EmailField
import app

def validate_email( email):
    email = email.data
    cur = app.getCursor()
    cur.execute(f"select count(email) from login where email='{email}';")
    email_count = cur.fetchone()
    if email_count[0] == 0:
        raise validators.ValidationError('This email is not registered')

class LoginForm(FlaskForm):
    email = EmailField('Email address *', validators=[validators.DataRequired(), validators.Email()])
    password = PasswordField(label='Password *', validators=[
        validators.DataRequired(),
        ])
    submit = SubmitField(label=('Login'))

    def validate_email(self, email):
        validate_email(email)



class resetPasswordForm(FlaskForm):
    email = EmailField('Email address *', validators=[validators.DataRequired(), validators.Email()])
    password = PasswordField(label='Password *', validators=[
    validators.DataRequired(),
    ])

    confirm_password = PasswordField(label='Confirm Password *', validators=[
        validators.DataRequired(),
        validators.EqualTo('password', message='The two passwords you have entered do not match.')
    ])
    submit = SubmitField(label=('Save'))
    def validate_email(self, email):
        validate_email(email)