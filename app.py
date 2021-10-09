#####################################################################
# Imports
#####################################################################

from flask import Flask, render_template, request, redirect, url_for, session
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
import psycopg2
import psycopg2.extras
import hashlib
import member_profile_form
from datetime import datetime, date, timedelta, time
import connect
import random
import uuid
from flask_mail import Mail, Message
import os
import calendar
import payment_form
import login_form

#####################################################################
# Global Functions
#####################################################################
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'any secret string'

dbconn = None
def getCursor():
    global dbconn
    if dbconn == None:
        conn = psycopg2.connect(dbname=connect.dbname, user=connect.dbuser,
                                password=connect.dbpass, host=connect.dbhost, port=connect.dbport)
        conn.autocommit = True
        dbconn = conn.cursor(cursor_factory = psycopg2.extras.NamedTupleCursor)
        return dbconn
    else:
        return dbconn


# generates random ID and checks that ID has not already been assigned
# takes parameters table (for the name of the table to be searched) 
#   and column_name (name of column in that table0)
def genID(table, column_name):
    unique_id = False
    cur = getCursor()
    while not unique_id:
        myid = random.randint(0, 9999)
        cur.execute(f"select count(*) from {table} where {column_name}={myid};")
        count = cur.fetchone()
        if count[0] == 0:
            unique_id = True
    return myid

# generates random 9-digit password with numbers and letters
def generate_password():
    password = str(uuid.uuid4())
    return password[-9:]

# hash the password before it is save into the Database
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Convert string to date object
def get_date(year, month, day):
    return datetime(year, month, day)

def get_today():
    return datetime.today().strftime('%Y-%m-%d')

def get_total_subscription_fee(subscription_type):
    if(subscription_type.lower() == 'weekly'):
        return 15
    elif(subscription_type.lower() == 'monthly'):
        return 60
    else:
        return 720





app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = connect.emailaddress
app.config['MAIL_PASSWORD'] = connect.emailpass
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True    

# parameters: title (str) -- email title
#             sender (str) -- address that will be sending the email
#             recipient (str) -- address that will get the email
#             body (str) -- text in the body of the email
def send_email(title, sender,recipient, body):
    mail = Mail(app)
    msg = Message(title, sender = sender, recipients = [recipient])
    msg.body = body
    mail.send(msg)


# upload photos configuration
app.config['UPLOADED_PHOTOS_DEST'] = os.path.join(basedir, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)   

weekday_list = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
def add_sessions(monday):
    cur = getCursor()        
    cur.execute(f"update login set email='{monday.date()}' where role='monday';")
    cur.execute('select classid, session_day from groupclasses;')
    classes = cur.fetchall()
    for groupclass in classes:
        sessionid = genID('groupsession', 'sessionid')
        session_delta = weekday_list.index(groupclass.session_day)
        session_date = monday + timedelta(days=session_delta)
        cur.execute(f"""insert into groupsession (sessionid, session_date, registrees, classid) 
                    values ({sessionid}, '{session_date.date()}', 0, {groupclass.classid});""")

def upsertMember(form, userid, action, trainer=False):
    first_name = form.first_name.data
    last_name = form.last_name.data
    dob = form.dob.data
    gender = form.gender.data
    address = form.address.data
    phone = form.phone.data
    emergency_name = form.emergency_name.data
    emergency_phone = form.emergency_phone.data
    email = form.email.data
                                   
    cur = getCursor()
    if trainer:
        specialties = form.specialties.data
        if not form.image.data:
            #if the image field was left blank
            cur.execute(f"select image from trainers where userid={userid};")
            image=cur.fetchall()[0]
        else:
            # the field was updated, insert new info
            filename = photos.save(form.image.data)
            image = photos.url(filename)
        cur.execute("UPDATE trainers SET first_name= %s, last_name= %s, phone= %s, gender= %s, address= %s, emergency_name= %s, emergency_phone= %s, image= %s, specialties= %s WHERE userid=%s;", \
                 (first_name, last_name, phone, gender, address, emergency_name, emergency_phone, image, specialties, userid))
    if action == 'insert':
        date_due = get_today()
        subscription_type = form.subscription_type.data
        amount_owed = 0 #because on first login, charge will accrue
        cur.execute("INSERT INTO members (userid, first_name, last_name, phone, email, gender, dob, address, emergency_name, emergency_phone,date_due, subscription_type,amount_owed, archived) \
                 VALUES (%s, %s,%s,%s,%s, %s, %s,%s,%s,%s,%s,%s,%s, FALSE);", (userid, first_name, last_name, phone, email, gender, dob, address, emergency_name, emergency_phone,date_due, subscription_type,amount_owed))
    else:
        cur.execute("UPDATE members SET first_name= %s, last_name= %s, phone= %s, gender= %s, address= %s, emergency_name= %s, emergency_phone= %s WHERE userid=%s;", \
                 (first_name, last_name, phone, gender, address, emergency_name, emergency_phone, userid))


def upsertUserIntoLoginTable(userid, email, password, role, action):
    cur = getCursor()
    if action == 'insert':
        cur.execute(f"INSERT into login values ({userid}, '{email}', '{password}', '{role}');")

def update_subscription_info(memberid):
    cur = getCursor()
    cur.execute(f"select * from members where userid={memberid};")
    member_info = cur.fetchone()
    amount_owed = member_info.amount_owed
    if member_info.archived:
        if amount_owed <= 0:
            cur.execute(f"update members set archived=FALSE where userid={memberid};")
        else:
            return "archived"
    today = datetime.today().date()
    date_due = member_info.date_due
    subscription = member_info.subscription_type
    if date_due > today and amount_owed <= 0:
        # member is paid into the future, no updates needed
        return
    fee = get_total_subscription_fee(subscription)
    new_amount_owed = amount_owed
    new_date_due = date_due
    while new_date_due <= today:
        # need to update subscription
        new_amount_owed += fee
        if subscription.lower() == 'weekly':
            new_date_due = new_date_due + timedelta(days = 7)
        elif subscription.lower() == 'monthly':
            new_date_due = new_date_due + timedelta(days = 30)
        else: #annual subscription 
            year = new_date_due.strftime('%Y')
            new_year = int(year) + 1
            new_date_due = new_date_due.replace(year=new_year)
    cur.execute(f"""update members set date_due='{new_date_due}', amount_owed = {new_amount_owed}
                    where userid={memberid};""")
    if new_amount_owed <= 0:
        return "up-to-date-payment"
    # subscription was updated but before that member was up to date with payments 

    else:
    # subscription was updated or else didn't need to be updated
    # but member was overdue on payments
    # need to check how long ago it renewed and if they are still in the window where they are allowed
        if subscription == 'Weekly':            
            if new_amount_owed > 30: # owe more than two weeks
                set_archived(memberid)
                return "archived"
            else:
                return "payment"
        elif subscription == 'Monthly':           
            past_date_due = date_due + timedelta(days=30)
        else: #yearly
            year = date_due.strftime('%Y')
            new_year = int(year) - 1
            past_date_due = date_due.replace(year=new_year) 
        two_weeks = past_date_due + timedelta(days=14)
        if two_weeks < today:
            set_archived(memberid)
            return "archived"
        else:
            return "payment"

def set_archived(memberid):
    cur = getCursor()
    cur.execute(f"update members set archived=True where userid={memberid};")

#####################################################################
# Custom Jinja Filters
#####################################################################

# custom filter to format datetime
# if the value passed is a datetime object, returns that value formatted
# otherwise returns the value without attempting to format
@app.template_filter()
def datetimefilter(value, format='%A, %B %d, %Y'):
    if isinstance(value, datetime) or isinstance(value, date):
        return value.strftime(format)
    else:
        return(value)

@app.template_filter()
def timefilter(value, format='%I:%M %p'):
    if isinstance(value, time):
        return value.strftime(format)
    else:
        return(value)

#####################################################################
# App routes
#####################################################################

#home page
@app.route("/")
def home():
    return render_template('home_page.html')


#return trainer lists page #
@app.route("/meet_trainer", methods=['GET'])
def meet_trainer():
    cur = getCursor()
    cur.execute("select userid, image, concat(first_name,' ', last_name) as name, gender, specialties from trainers where archived = False order by name ASC;")
    select_result = cur.fetchall()
    return render_template ('meet_trainer.html',db_trainer=select_result)


# NOTE: needs to add email being sent to trainer with password functionality
# add a new trainer
# available only to the manager
@app.route("/add_trainer", methods=['GET', 'POST'])
def add_trainer():
    form = member_profile_form.TrainerProfileForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            userid = genID('Login', 'userid')
            first_name = form.first_name.data
            last_name = form.last_name.data
            email = form.email.data
            phone = form.phone.data
            password = generate_password()
            dob = form.dob.data
            gender = form.gender.data
            address = form.address.data
            phone = form.phone.data
            emergency_name = form.emergency_name.data
            emergency_phone = form.emergency_phone.data
            specialties = form.specialties.data
            if not form.image.data:
                file_url='http://127.0.0.1:5000/_uploads/photos/silhouette.png'
            else:
                filename = photos.save(form.image.data)
                file_url = photos.url(filename)
            cur = getCursor()
            # adds trainer to the login table
            cur.execute(f"insert into login values ({userid}, '{email}', '{password}', 'trainer');")
            # adds trainer to the trainers table           
            cur.execute(f"""insert into trainers (userid, first_name, last_name, email, address,
            phone, image, dob, gender, emergency_name, emergency_phone, specialties, archived) values
            ({userid}, '{first_name}', '{last_name}', '{email}', '{address}', '{phone}', '{file_url}', '{dob}', 
            '{gender}', '{emergency_name}', '{emergency_phone}', '{specialties}', FALSE); """)
            # sends an email for the trainer to reset their password
            body = """Welcome to Lincoln Uni Fitness! 
Here is a link to set up your password: http://127.0.0.1:5000/reset_password
You will then be able to log in to our system."""
            send_email(title='Welcome to LU Fitness', sender=connect.emailaddress,
                recipient=email, body=body)
            message = f"You have successfully added {first_name} {last_name}. They will recieve an email shortly to finish setting up their account."
            return render_template ('message.html', message=message)
        else:
            # if form is posted but not validated
            return render_template('add_trainer.html', form=form)
    else:
        return render_template('add_trainer.html', form=form)


#add a new member for manager or member
@app.route("/add_new_member", methods=['GET','POST'], endpoint='v1')
@app.route("/member_registration", methods=[ 'GET','POST'], endpoint='v2')
def add_member():
    form = member_profile_form.MemberProfileForm()
    version = request.endpoint
    userid = genID('Login', 'userid')
    successful_message = None
    email_body = None
    if version == 'v1':
        form = member_profile_form.MemberProfileForm()
        password = generate_password()
        successful_message = "New member has been added. An confirmation email will be sent to the new member"
        email_body = """Welcome to Lincoln Uni Fitness! 
Here is a link to set up your password: http://127.0.0.1:5000/reset_password
You will then be able to log in to our system."""
        pass
    else:
        form = member_profile_form.MemberRegistrationForm()
        password = form.password.data
        successful_message = "You have signed up successfully. An confirmation email will be sent to your email address"
        email_body = "You have signed up successfully. You can login with your email address"
        pass
    if form.validate_on_submit():
        password = hash_password(password)
        email = form.email.data  
        upsertMember(form, userid, 'insert')
        upsertUserIntoLoginTable(userid, email, password, 'member','insert')

        # Send an email to the new member        
        send_email(title='Welcome to LU Fitness', sender=connect.emailaddress,
        recipient=email, body=email_body)

        return render_template ('message.html',message= successful_message, home=True)
 
    else:
        return render_template('member_registration.html', form=form, version = version)       


#view and update member profile
@app.route("/update_member_profile", methods=['GET', 'POST'], endpoint='update_member_profile')
@app.route("/view_member_profile", methods=['GET'], endpoint='view_member_profile')
def member_profile():
    version = request.endpoint
    form = member_profile_form.MemberProfileForm()
    user_id = None
    readonly: bool 

    if session['role'] == 'member':
        user_id = session['id']
    else: 
        user_id = request.args.get('member_id')

    if(version == 'update_member_profile'):
        readonly = False
    else:
        readonly = True

    cur = getCursor()
    cur.execute(f"SELECT * from members Where userid = {user_id};")
    member = cur.fetchone()

    if request.method == 'POST':
        form.subscription_type.data = member.subscription_type
        if form.validate_on_submit():
            upsertMember(form, user_id, 'update')
            return render_template('message.html',message="You have updated the profile successfully")
    
        else:
            print(form.errors)
            return render_template('member_profile.html', form=form, readonly = readonly, version = version, user_id= user_id)
    else:               
        form.first_name.data= member.first_name
        form.last_name.data= member.last_name
        form.email.data= member.email
        form.dob.data=member.dob
        form.gender.data= member.gender
        form.address.data= member.address
        form.phone.data= member.phone
        form.emergency_name.data= member.emergency_name
        form.emergency_phone.data= member.emergency_phone

        return render_template('member_profile.html', form=form, readonly = readonly, version = version, user_id= user_id, member=member)



@app.route("/archive_member", methods=['GET'])
def archive_member():
    member_id = request.args.get('member_id')
    cur = getCursor()
    cur.execute(f"UPDATE members SET archived= TRUE WHERE userid={member_id};")
    return render_template('message.html',message=f"Member {member_id} has been archived")

#return member list page #
@app.route("/archived_member_list", methods=['GET'], endpoint='archived_member_list')
@app.route("/member_list", methods=['GET'], endpoint='active_member_list')
def view_all_members(): 
    version = request.endpoint
    are_archived = False
    if(version == 'archived_member_list'):
        are_archived = True

    cur = getCursor()
    cur.execute(f"select userid, concat(first_name,' ', last_name) as name, email from members where archived = {are_archived} order by name ASC;")
    column_names = [desc[0] for desc in cur.description]
    select_result = cur.fetchall()    
    return render_template ('member_list_table.html',db_members=select_result, column_names = column_names, are_archived = are_archived)

# view and update subscription
@app.route("/subscription", methods=['GET','POST'])
def subscription():
    # subscription type fee 
    user_id = session['id']
    cur = getCursor()
    cur.execute(f"select email, subscription_type, date_due, amount_owed from members where userid= {user_id};")
    result = cur.fetchone()
    subscription_type=result.subscription_type

    if request.method=="POST":
        #get update new subcription type
        subscription=request.form.get('subscription')
        # once current subscription type == new subscription type show the action faild.
        # return to message.html, reselect new subscription  
        if  subscription_type == subscription:
            return render_template ('message.html', message= f"The action has failed. You already have that type of subscription",
                                    return_subscription=True )
        else:
            cur.execute(f"update members set subscription_type='{subscription}' where userid={user_id};")
            return render_template ('message.html',  member_dashboard=True, 
                                    message= "Your subscription have changed! You will receive a copy of your receipt in your email shortly.")
    else:
        return render_template ("subscription.html",result=result,subscription=subscription_type)


@app.route("/make_a_payment", methods=['GET', 'POST'])
def make_a_payment():
    user_id = session['id']
    weekly_subscription_fee = 15
    cur = getCursor()
    cur.execute(f"select amount_owed, email, subscription_type, date_due from members where userid= {user_id};")
    result = cur.fetchone()
    amount_owed = result.amount_owed
    email = result.email
    subscription_type = result.subscription_type
    subscription_fee = get_total_subscription_fee(subscription_type)
    date_due = result.date_due
    # get number of weeks that members can choose for
    num_to_pay_for = []
    form = payment_form.PaymentForm()
    if amount_owed > 0:
        num_to_pay_for = [f'${amount_owed}']
        form.num_of_weeks_pay_for.label = "Pay the balance on your account"
    elif subscription_type.lower() == 'weekly':
        num_to_pay_for = ['1', '2', '3', '4']
    elif subscription_type.lower() == 'monthly':
        form.num_of_weeks_pay_for.label = 'Number of months to pay for'
        num_to_pay_for = ['1', '2', '3']
    else:
        form.num_of_weeks_pay_for.label = 'Pay for one year'
        num_to_pay_for = ['1']
    form.num_of_weeks_pay_for.choices = num_to_pay_for
    if request.method == 'POST':
        if form.validate_on_submit():
            payment_id = genID('payments', 'paymentid')
            num_to_pay_for = form.num_of_weeks_pay_for.data
            description = 'subscription'
            if amount_owed > 0:
                amount_paid = amount_owed
            else:
                amount_paid = int(num_to_pay_for) * subscription_fee
            balance = amount_owed - amount_paid
            date = get_today()

            cur.execute(f"UPDATE members SET amount_owed= {balance} WHERE userid={user_id};")
            cur.execute(f"insert into payments values ({payment_id}, '{date}',{amount_paid},'{description}',{user_id});")

            body = f"Here is your payment receipt. You have paid ${amount_paid} for {description}"
            send_email(title='Payment Receipt', sender=connect.emailaddress,
                recipient=email, body=body)
            return render_template ('message.html',message= "Your payment has been received! You will receive a copy of your payment receipt in your email shortly.")
        else:
            return render_template("payment_form.html", form=form, amount_owed=amount_owed, 
            subscription_type = subscription_type, date_due=date_due, subscription_fee=subscription_fee)
    else:     
        return render_template ('payment_form.html',form = form, amount_owed= amount_owed, 
        subscription_type = subscription_type, date_due=date_due, subscription_fee=subscription_fee)
        
#View trainer schedule as trainer
@app.route("/trainer_schedule", methods=['GET'])
def trainer_schedule():
    trainer_id = session['id']  
    cur = getCursor()
    today= get_today() 
    cur.execute(f"select class_name, session_day, session_time, duration from groupclasses WHERE trainerid= {trainer_id};")
    class_result=cur.fetchall()
    cur.execute(f"""select session_date, session_time, first_name, last_name from training 
                left join members on members.userid = training.memberid WHERE trainerid= {trainer_id} 
                and session_date >= '{today}' order by session_date asc;""")
    select_result = cur.fetchall()  
    return render_template ('trainer_schedule.html',db_training=select_result, class_result= class_result)

#Update trainer schedule
@app.route("/update_trainer_schedule", methods=['GET', 'POST'])
def update_trainer_schedule():
    form = member_profile_form.TrainerScheduleForm()
    trainerid = session['id']
    if request.method == 'POST':
        if form.validate_on_submit():
            session_date = form.session_date.data
            session_time = form.session_time.data
            cur = getCursor()
            # find out if the session overlaps with any classes or personal training sessinos
            session_weekday = session_date.strftime('%A') # gets the session_date as a word for the day of the week
            overlap_start = (datetime.combine(session_date, session_time) - timedelta(minutes=60)).time() # 1 hr before the desired booking time
            overlap_finish = (datetime.combine(session_date, session_time) + timedelta(minutes=59)).time() # 59 mins after desired booking time
            # checks training session table
            cur.execute(f"""select count(*) from training where trainerid={trainerid} and 
                        session_date='{session_date}' and session_time >= '{overlap_start}' and session_time <= '{overlap_finish}';""")
            count1 = cur.fetchall()[0]
            # checks group classes table
            cur.execute(f"""select count(*) from groupclasses where trainerid={trainerid} and session_day='{session_weekday}' 
                        and session_time >= '{overlap_start}' and session_time <= '{overlap_finish}';""")
            count2 = cur.fetchall()[0]
            if (count1.count+count2.count) != 0:
                # then there is a conflic of times
                return render_template('update_trainer_schedule.html', form=form, 
                message='This time conflicts with another personal training or group class on your schedule')
            else:
                trainingid = genID("training", "trainingid")
                cur.execute(f"INSERT INTO training (trainerid, trainingid, session_date, session_time) VALUES ({trainerid}, {trainingid}, '{session_date}','{session_time}');")
            return redirect("/trainer_schedule")
        else:
            print(form.errors)
            return render_template("update_trainer_schedule.html", form=form)
    else:          
        return render_template('update_trainer_schedule.html', form=form)

#view trainer schedule as member
@app.route("/book_personal_training", methods=['GET'])
def book_personal_training():
    trainer_id = request.args.get("trainer_id") 
    cur = getCursor()
    today= get_today() 
    now = datetime.now().time()
    cur.execute(f"""select * from training WHERE trainerid= {trainer_id}
                and session_date >= '{today}' and memberid is null order by session_date asc;""")
    select_result = cur.fetchall() 
    return render_template ('book_personal_training.html',db_training=select_result)

#book personal training and pay
@app.route("/book_and_pay", methods=['GET','POST'])
def book_and_pay():
    form = member_profile_form.TrainerScheduleForm()
    sessionid= request.args.get("sessionid")
    memberid = session['id']
    cur = getCursor()
    cur.execute(f"select * from training where trainingid={sessionid};")
    session_data = cur.fetchall()[0]
    form.session_date.data = session_data.session_date
    form.session_time.data = session_data.session_time
    if request.method == 'POST':
        if form.validate_on_submit():
            paymentid = genID('payments', 'paymentid')
            today = get_today()
            cur.execute(f"UPDATE training SET memberid = {memberid} where trainingid={sessionid};")
            cur.execute(f"""INSERT INTO payments (paymentid, pay_date, amount, description, userid)
                        VALUES ({paymentid}, '{today}', 50, 'training', {memberid});""")
            cur.execute(f"select email from members where userid={memberid};")
            email = cur.fetchall()[0]
            body = "Your payment of 50 dollars for a personal training session has been received."
            send_email('Payment Recieved', connect.emailaddress, email.email, body)
            return render_template("message.html", message="Your payment has been successful.")
        else: 
            return render_template ('book_and_pay.html', form=form)
    else: 
        return render_template ('book_and_pay.html', form=form)

#Check-In Dasboard
@app.route("/check_in", methods=['GET','POST'])
def check_in():
    if request.method == 'POST':
        checkin_date=datetime.today().strftime('%Y-%m-%d')
        checkin_time=datetime.now().strftime('%H:%M:%S')
        user_id = session['id']
        cur = getCursor()
        cur.execute("INSERT INTO GymAttendance VALUES (%s,%s,%s);",(checkin_date,checkin_time,user_id))
        return redirect(url_for('member_dashboard'))
    else:    
        return render_template('check_in.html')     

#Dashboards
@app.route("/manager_dashboard", methods=['GET'])
def manager_dashboard():
    return render_template('manager_dashboard.html')

@app.route("/member_dashboard", methods=['GET'])
def member_dashboard():
    return render_template('member_dashboard.html')

@app.route("/trainer_dashboard", methods=['GET'])
def trainer_dashboard():
    return render_template('trainer_dashboard.html')

#Session Check-In
@app.route("/session_checkin", methods=['GET','POST'])  
def session_checkin(): 
    member_id = session['id']
    session_date=request.form.get('session_date')
    session_time=request.form.get('session_time')
    cur = getCursor()
    today = get_today()
    cur.execute(f"""SELECT concat(first_name,' ', last_name) as name, session_date, session_time 
    FROM trainers join training on trainers.userid=training.trainerid 
    where attendance_status is null and memberid={member_id} and session_date='{today}';""")
    select_result = cur.fetchall()
    if request.method == 'POST': 
        cur.execute("INSERT INTO GymAttendance VALUES (%s,%s,%s);",(session_date,session_time,member_id))
        cur.execute(f"Update training SET attendance_status='Present' where memberid={member_id};")
        return redirect(url_for('member_dashboard'))
    else:
        return render_template('session_checkin.html',session_check=select_result)

#Class check-in
@app.route("/class_checkin", methods=['GET','POST'])  
def class_checkin():
    user_id = session['id']
    session_date=request.form.get('session_date')
    today = get_today()
    session_time=request.form.get('session_time')
    cur = getCursor()
    cur.execute(f"""SELECT class_name, session_date, session_time FROM groupclasses 
    JOIN GroupSession ON groupclasses.classid = groupsession.classid 
    JOIN sessionmembers ON sessionmembers.sessionid = groupsession.sessionid 
    JOIN members ON members.userid=sessionmembers.memberid 
    WHERE attendance_status is null and memberid={user_id} and session_date='{today}';""")
    select_result = cur.fetchall()
    if request.method == 'POST': 
        cur.execute("INSERT INTO GymAttendance VALUES (%s,%s,%s);",(session_date,session_time,user_id))
        cur.execute(f"Update sessionmembers SET attendance_status='Present' where memberid={user_id};")
        return redirect(url_for('member_dashboard'))
    else:
        return render_template('class_checkin.html', checkclass_result=select_result)

# view a trainer’s profile as a member
@app.route("/find_trainer", methods=['GET','POST'])
def find_trainer():
    user_id = request.args.get('trainer_id')
    cur = getCursor()
    cur.execute(f"SELECT * from trainers Where userid = {user_id};")
    trainer = cur.fetchone()
    if request.method == 'POST':
        return redirect(url_for('member_dashboard'))
    else:
        return render_template ('find_trainer.html',result=trainer)


# view and book group class schedule 
@app.route("/group_class_calendar", methods=['GET', 'POST'])
def group_class_calendar():
    memberid = session['id']
    cur = getCursor()
    message = None
    # get memberid to run SQL
    if request.method == 'POST':
        sessionid = request.form.get("sessionid")
        now = datetime.now().time()
        cur.execute(f"select session_time, session_date from groupclasses join groupsession using(classid) where sessionid={sessionid};")
        class_time = cur.fetchall()[0]
        if now > class_time.session_time and datetime.today().date() == class_time.session_date:
            message = "You cannot book this class as it has already occured today"
        else:
            # adds member to sessionmembers table
            cur.execute(f"insert into sessionmembers (sessionid, memberid) values ({sessionid}, {memberid});")
            # increases number of registrees for that session by 1
            cur.execute(f"select registrees from groupsession where sessionid={sessionid};")
            registrees = cur.fetchone()[0] + 1
            cur.execute(f"update groupsession set registrees={registrees} where sessionid={sessionid};")
            message = 'You have succesfully booked your class!'
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 
                'Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',]
    # returns weekday as an integer where Mon is 0
    weekday = datetime.today().weekday() 
    # gets a list of names of days for one week starting from tomorrow
    day_names = day_names[(weekday):(weekday + 7)]
    # returns today's date
    today = int(datetime.today().strftime('%d'))
    # get the date of the next monday
    delta_days = 7 - weekday
    next_monday = datetime.today() + timedelta(days=delta_days)
    # get the date of a Monday which is stored in login database
    # that Monday is the date for which sessions have been created in groupsessions table for that week
    cur.execute("select email from login where role='monday';")
    result = cur.fetchone()[0]
    # checks to see if next monday is the same date as the monday stored in the login table
    # if not, will need to add sessions
    if result != next_monday.strftime('%Y-%m-%d'):
        add_sessions(next_monday)
    # gets session info for the week starting from today
    first_date = datetime.today().date()
    second_date = first_date + timedelta(days=6)
    # creates a view that only contains the sessions where the member has booked
    # uses a left join to join to the session info so that if the member has booked the clases, memberid=memberid
    cur.execute(f"create or replace view specific_sessionmember as select * from sessionmembers where memberid={memberid};")
    cur.execute(f"""select groupclasses.class_name, groupclasses.session_time, 
        groupsession.registrees, groupsession.sessionid, groupsession.session_date,
        specific_sessionmember.memberid from groupsession 
        join groupclasses using(classid) left join specific_sessionmember using(sessionid)
        where groupsession.session_date >= '{first_date}' 
        and groupsession.session_date <= '{second_date}' ;""") 
    session_info = cur.fetchall() 

    # creates a list containing lists that look like:
    # [date_number, [sessioninfo_tuples_on_that_date, there_may_be_several]]
    day_date = first_date
    weekdates = []
    for day in calendar.day_name:  #calendar.day_name is a list of seven days of the week
        # gets date number
        weekdate = int(day_date.strftime('%d')) 
        sessions = []
        for info in session_info:
            # if the date of that session is the same as the weekdate
            # adds that session tuple to a list
            if info.session_date == day_date:
                sessions += [info]
        # creates list for the date and adds it to larger list of the week
        weekdates += [[weekdate, sessions]]
        # adds one day to the date for next iteration of for loop
        day_date = day_date + timedelta(days=1)   
    return render_template ('group_class_calendar.html', weekdates=weekdates, day_names=day_names, memberid=memberid, message=message)

#view and update trainer profile
@app.route("/update_trainer_profile", methods=['GET', 'POST'], endpoint='update_trainer_profile')
@app.route("/trainer_profile", methods=['GET'], endpoint='view_trainer_profile')
def update_trainer_profile():
    version = request.endpoint
    form = member_profile_form.TrainerProfileForm()
    user_id = None
    readonly:bool


    if session['role'] =='trainer':
        user_id=session['id']
    else:
        user_id=request.args.get('user_id')


    if (version =='update_trainer_profile'):
        readonly=False
    else:
        readonly=True

    cur = getCursor()
    cur.execute(f"SELECT * from trainers Where  userid = {user_id};")
    trainer = cur.fetchone()
    if request.method == 'POST':
        if form.validate_on_submit():
            upsertMember(form, user_id, 'update', trainer=True)
            return render_template('message.html',message="You have updated the profile successfully")
    
        else:
            print(form.errors)
            return render_template('trainer_profile.html', form=form, readonly=readonly, version = version, trainer=trainer)

    
    form.first_name.data= trainer.first_name
    form.last_name.data= trainer.last_name
    form.email.data= trainer.email
    form.dob.data= trainer.dob
    form.gender.data= trainer.gender
    form.address.data= trainer.address
    form.phone.data= trainer.phone
    form.emergency_name.data= trainer.emergency_name
    form.emergency_phone.data= trainer.emergency_phone
    form.specialties.data = trainer.specialties
    if not form.image.data:
        #if the image field was left blank
        cur.execute(f"select image from trainers where userid={user_id};")
        image=cur.fetchall()[0]
    else:
        # the field was updated, insert new info
        filename = photos.save(form.image.data)
        image = photos.url(filename)
              
    return render_template('trainer_profile.html', form=form, readonly=readonly, version = version, trainer=trainer)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = login_form.LoginForm()
    if request.method == 'POST':        
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            password = hash_password(password)

            cur = getCursor()
            cur.execute(f"SELECT * from login Where email = '{email}' AND password = '{password}';")
            user = cur.fetchone()
            # Create session data, we can access this data in other routes
            if user:                 
                session['loggedin'] = True
                session['id'] = user.userid
                session['name'] = user.name
                session['username'] = user.email
                session['role'] = user.role

                if session['role'] == 'member':
                    # check and update subscription information
                    subscription_return = update_subscription_info(session['id'])
                    if subscription_return == 'up-to-date-payment':
                        message = """Your subscription has rolled over, but you are still in credit.
If you want more information on your subscription, click the button below."""
                        return render_template('message.html', message=message, payment=True)
                    elif subscription_return == 'payment':
                        message = """You currently owe money on your account.
In order to keep your account active, please go to the payments page to settle your account."""
                        return render_template('message.html',message=message, payment=True)
                    elif subscription_return == 'archived':
                        message = """We're sorry, but your account is currently inactive. 
This may be due to unpaid membership fees. You currently only have access to our payment portal.
To reactivate your account, make a full payment, log out, and log back in.
Please contact the gym at lincolnunifitness@gmail.com with any further questions."""
                        return render_template('message.html', message=message, payment=True)
                url = f"/{user.role}_dashboard"
                return redirect(url)
            else:
                return render_template('login.html', form= form, message="Account doesn't exist or username/password incorrect")
        else:
            return render_template('login.html', form= form)
    else:
        return render_template('login.html', form= form)

@app.route("/logout", methods=['GET', 'POST'])
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('name', None)
    session.pop('username', None)
    session.pop('role', None)
    # Redirect to login page
    return redirect(url_for('login'))

@app.route("/financial_report", methods=['GET', 'POST'])
def view_finacial_report():
    if request.method =="POST":
        start_date = request.form.get("from")
        end_date = request.form.get("to")
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")        
    else:
        today_date = get_today()
        start_date =  datetime.strptime('2021-03-01', "%Y-%m-%d")
        end_date = datetime.strptime(today_date, "%Y-%m-%d")
    
    cur = getCursor()
    # Total Income Table
    cur.execute(f"select LOWER(description) as Category, sum(amount) as Income from payments WHERE pay_date BETWEEN '{start_date}' AND '{end_date}' group by LOWER(description);")
    income_result_column_names = [desc[0] for desc in cur.description]
    income_result = cur.fetchall()
    cur.execute(f"select sum(amount) as total_income from payments WHERE pay_date BETWEEN '{start_date}' AND '{end_date}';")
    total_income = cur.fetchone().total_income

    # Outstanding payments table
    cur.execute("select userid, concat(first_name,' ', last_name) as name, amount_owed as outstanding from members where amount_owed > 0;")
    outstanding_payments_result_column_names = [desc[0] for desc in cur.description]
    outstanding_payments_result = cur.fetchall()
    cur.execute("select sum(amount_owed) as total_outstanding from members where amount_owed > 0;")
    total_outstanding = cur.fetchone().total_outstanding

    # Received Payments table
    cur.execute(f"select members.userid, concat(members.first_name,' ', members.last_name) as name, grouped_payment.total\
                from (select sum(amount) as total, payments.userid from payments WHERE pay_date BETWEEN '{start_date}' AND '{end_date}' group by payments.userid) grouped_payment Join members\
                on  grouped_payment.userid = members.userid;")
    received_payment_result_column_names = [desc[0] for desc in cur.description]
    received_payment_result = cur.fetchall()
    cur.execute("SELECT  COUNT(DISTINCT userid) from payments;")
    members_paid_count = cur.fetchone().count

    cur.execute("select count(userid) as members_count from members;")
    members_count = cur.fetchone().members_count
    
    return render_template('financial_report.html', 
    start_date = start_date,
    end_date = end_date,
    income_result_column_names=income_result_column_names,
    income_result=income_result,
    total_income =total_income,
    outstanding_payments_result_column_names = outstanding_payments_result_column_names,
    outstanding_payments_result = outstanding_payments_result,
    total_outstanding = total_outstanding,
    received_payment_result_column_names = received_payment_result_column_names,
    received_payment_result = received_payment_result,
    members_paid_count = members_paid_count,
    members_count = members_count )

@app.route("/add_class", methods=['GET', 'POST'])
def add_class():
    cur=getCursor()
    if request.method =="POST":
        classid=genID('groupclasses','classid')
        class_name=request.form.get('class_name')
        description=request.form.get('description')
        day=request.form.get('day')
        session_time=request.form.get('session_time')
        duration=request.form.get('duration')
        trainerid=request.form.get('trainerid')
        sessionid = genID('groupsession', 'sessionid')
        # get date of the next session
        today = datetime.today().date()
        today_int = today.weekday() #returns day as an integer where Mon is 0
        class_day = weekday_list.index(day) #returns day as an integer using global weekday_list
        day_delta = class_day - today_int
        if day_delta >= 0:
            # less than 0  means that the class doesn't occur until next week
            # this means the next session will be automatically generated by the group_class_calendar page
            # > 0 means need to generate class 
            session_date = today + timedelta(days=day_delta)
            cur.execute(f"""insert into groupsession (sessionid, session_date, registrees,classid) 
                values ({sessionid}, '{session_date}', 0, {classid});""")
        cur.execute(f"""insert into groupclasses values
        ({classid},'{class_name}','{description}','{day}','{session_time}','{duration}',{trainerid});""")
        return redirect(url_for('manager_dashboard'))
    else:
        cur.execute("select * from trainers where archived = False;")
        result=cur.fetchall()
        return render_template("add_class.html",class_result=result)

@app.route("/check_attendance", methods=['GET', 'POST'])
def check_attendance():
    cur = getCursor()
    if request.method == 'POST':
        start_date = request.form.get("from")
        end_date = request.form.get("to")
        start_date = datetime.strptime(start_date, "%m/%d/%Y")
        end_date = datetime.strptime(end_date, "%m/%d/%Y")
        attendance_dict = {}
        if session['role'] == 'manager':
            # get gym checkin attendance info and add to dictionary
            cur.execute(f"select count(*) from gymattendance where checkin_date >= '{start_date}' and checkin_date <= '{end_date}';")
            total_gym = cur.fetchone()[0]
            attendance_dict["total_gym"] = total_gym
            cur.execute(f"select count(distinct userid) from gymattendance where checkin_date >= '{start_date}' and checkin_date <= '{end_date}';")
            unique_gym = cur.fetchone()[0]
            attendance_dict["unique_gym"] = unique_gym
            # get training attendance info and add to dictionary
            cur.execute(f"select count(*) from training where session_date >= '{start_date}' and session_date <= '{end_date}';")
            total_training = cur.fetchone()[0]
            attendance_dict["total_training"] = total_training
            cur.execute(f"select count(distinct memberid) from training where session_date >= '{start_date}' and session_date <= '{end_date}';")
            unique_training = cur.fetchone()[0]
            attendance_dict["unique_training"] = unique_training
            # get group class attendance info and add to dictionary
            cur.execute(f"""select count(*) from sessionmembers left join groupsession using (sessionid) 
                        where session_date >= '{start_date}' and session_date <= '{end_date}';""")
            total_class = cur.fetchone()[0]
            attendance_dict["total_class"] = total_class
            cur.execute(f"""select count(distinct memberid) from sessionmembers left join groupsession using (sessionid) 
                        where session_date >= '{start_date}' and session_date <= '{end_date}';""")
            unique_class = cur.fetchone()[0]
            attendance_dict["unique_class"] = unique_class
            # get a list of how many members have attended a session with each trainer
            cur.execute(f"""create or replace view trainer_count as select trainerid, count(*) from training 
                        where session_date >= '{start_date}' and session_date <= '{end_date}' group by trainerid;""")
            cur.execute("select first_name, last_name, count from trainer_count join trainers on trainers.userid = trainer_count.trainerid order by count desc;")
            trainer_count = cur.fetchall()
            # get a list of how many members have attended each class
            cur.execute(f"""create or replace view class_count as select classid, count(*) from groupsession
                        join sessionmembers using(sessionid) where session_date >= '{start_date}' and session_date <= '{end_date}'
                        and attendance_status is not null group by classid;""") 
            cur.execute("select class_name,count from class_count join groupclasses using(classid) order by count desc;")
            class_count = cur.fetchall() 
        elif session['role'] == 'trainer':
            trainerid = session['id']
            cur.execute(f"""select count(*) from training where session_date >= '{start_date}' 
                        and session_date <= '{end_date}' and trainerid={trainerid};""")
            total_training = cur.fetchone()[0]
            attendance_dict["total_training"] = total_training
            cur.execute(f"""select count(distinct memberid) from training where session_date >= '{start_date}' 
                        and session_date <= '{end_date}' and trainerid={trainerid};""")
            unique_training = cur.fetchone()[0]
            attendance_dict["unique_training"] = unique_training
            cur.execute(f"""create or replace view class_count as select classid, count(*) from groupsession
                        join sessionmembers using(sessionid) where session_date >= '{start_date}' and session_date <= '{end_date}'
                        and attendance_status is not null group by classid;""")
            cur.execute(f"""select class_name,count from class_count join groupclasses 
                        using(classid) where trainerid={trainerid} order by count desc;""")
            class_count = cur.fetchall() 
            trainer_count = None   
        return render_template('check_attendance.html', posted=True, trainer_count=trainer_count, 
        class_count=class_count, attendance_dict=attendance_dict, start_date=start_date.date(), end_date=end_date.date())
    else:
        return render_template('check_attendance.html', posted=False)

@app.route("/update_archive_trainer", methods=['GET', 'POST'])
def update_archive_trainer():
    trainer_id=request.form.get('trainerid')
    cur = getCursor()
    if request.method == 'POST':
        cur.execute(f"update trainers SET archived= TRUE WHERE userid={trainer_id}")
    cur.execute(f"select userid,concat(first_name,' ',last_name) as name, email from trainers where archived = FALSE order by name ASC;")
    record=cur.fetchall()
    return render_template('update_archive_trainer.html',record=record)

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_password():
    form = login_form.resetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            password = hash_password(password)
            cur=getCursor()
            cur.execute("Update login SET password=%s where email=%s;", (password,email))
            return render_template ('message.html', message="Your password has been reset successfully", home=True)
        else:
            return render_template('reset_password_form.html', form= form)
    else:
        return render_template('reset_password_form.html', form= form)

@app.route("/member_schedule")
def member_schedule():
    cur = getCursor()
    userid = session['id']
    today = get_today()
    cur.execute(f"""select first_name, last_name, session_date, session_time from training
                join trainers on trainers.userid = training.trainerid
                where memberid = {userid} and session_date >= '{today}' order by session_date asc;""")
    trainer_count = cur.fetchall()
    cur.execute(f"""select class_name, session_date, session_time from sessionmembers
                join groupsession using(sessionid) join groupclasses using(classid)
                where memberid = {userid} and session_date >= '{today}' order by session_date asc;""")
    class_count = cur.fetchall()
    return render_template('member_schedule.html', trainer_count=trainer_count, class_count=class_count)

@app.route("/newsletter", methods=['GET','POST'])
def newsletter():
    if request.method == 'POST':
        title = request.form.get("title")
        body = request.form.get("body")
        cur = getCursor()
        cur.execute("select email from members where archived is not null;")
        members = cur.fetchall()
        for member in members:
            send_email(title=title, sender=connect.emailaddress,
                      recipient=member.email, body=body)
        return render_template('message.html', message='Your newsletter has been sent!')
    return render_template('newsletter.html')

@app.route("/member_subscriptions", methods=['GET','POST'])
def member_subscriptions():
    cur = getCursor()
    today = datetime.today()
    five_days = today + timedelta(days=5)
    cur.execute(f"""select count(*) from members where date_due >= '{today}' 
                and date_due <= '{five_days}' and amount_owed > 0 and archived = False;""")
    soon_count = cur.fetchone()[0]
    cur.execute(f"select count(*) from members where amount_owed > 0 and archived = False;")
    overdue_count = cur.fetchone()[0]
    if request.method == 'POST':
        email_type = request.form.get("type")
        if email_type == 'soon':
            title = "Membership Renewal"
            body = """Your membership at Lincoln Uni Fitness will renew in 5 days or less. 
Please log in and make a payment to avoid your account being rendered inactive."""
            cur.execute(f"select email from members where date_due >= '{today}' and date_due <= '{five_days}' and archived = False;")
        elif email_type == 'overdue':
            title = "Account Payment Overdue"
            body = """Your membership payment at Lincoln Uni Fitness is overdue.
Please log in and make a payment to avoid your account being rendered inactive."""            
            cur.execute(f"select email from members where amount_owed > 0 and archived = False;")
        members = cur.fetchall()
        for member in members:
            send_email(title=title, sender=connect.emailaddress,
                      recipient=member.email, body=body)
        return render_template('message.html', message='Your emails have been sent!')
    return render_template('member_subscriptions.html', overdue_count=overdue_count, soon_count=soon_count)

@app.errorhandler(413)
def request_entity_too_large(error):
    return redirect('message.html', message="Your file is too large! It must be less than 1 GB."), 413