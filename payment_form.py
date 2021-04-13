from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectField, validators
from wtforms.fields.html5 import IntegerField
import app

class PaymentForm(FlaskForm):  
    num_of_weeks_pay_for = SelectField(label='Number of weeks to pay for', validators =[validators.DataRequired()])
    submit = SubmitField(label=('Submit'))





