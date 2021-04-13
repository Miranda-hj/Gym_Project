DROP TABLE IF EXISTS members CASCADE;
CREATE TABLE members (
    userid smallint,
    first_name character varying(40),
    last_name character varying(40),
    email character varying(60),
    phone character varying(60),
    address character varying(60),
    dob date,
    gender character varying(40),
    emergency_name character varying(40),
    emergency_phone character varying(60),
    subscription_type character varying(40),
    amount_owed smallint,
    date_due date,
    archived boolean
);

DROP TABLE IF EXISTS trainers CASCADE;
CREATE TABLE trainers (
    userid smallint,
    first_name character varying(40),
    last_name character varying(40),
    email character varying(60),
    phone character varying(60),
    address character varying(60),
    image character varying(60),
    dob date,
    gender character varying(40),
    emergency_name character varying(40),
    emergency_phone character varying(60),
    specialties text,
    archived boolean
);


CREATE TABLE training (
    trainingid smallint,
    session_date date,
    session_time time,
    attendance_status character varying(40),
    memberid smallint,
    trainerid smallint
);


CREATE TABLE gymattendance (
    checkin_date date,
    checkin_time time,
    userid smallint
);


CREATE TABLE groupclasses (
    classid smallint,
    class_name character varying(40),
    class_description text,
    session_day character varying(40),
    session_time time,
    duration smallint,
    trainerid smallint
);


CREATE TABLE groupsession (
    sessionid smallint,
    session_date date,
    registrees smallint,
    classid smallint
);


CREATE TABLE sessionmembers (
    sessionid smallint,
    memberid smallint,
    attendance_status character varying(40)
);


CREATE TABLE payments (
    paymentid smallint,
    pay_date date,
    amount smallint,
    description character varying(40),
    userid smallint
);

DROP TABLE IF EXISTS login CASCADE;
CREATE TABLE login (
    userid smallint,
    email character varying(60),
    password character varying(256),
    role character varying(40)
);

INSERT INTO members VALUES (100, 'Rita', 'Kester',
'rita@tester.com', '000-111-1111', '100 Manuel St, Christchurch 8014',
'1960-05-31', 'Female', 'Benjamin', '023-933-2030',
'monthly', 50, '2021-04-01', FALSE);

INSERT INTO members VALUES (202, 'Sydney', 'Harris',
'sydney@tester.com', '000-111-1111', '1/14 Merry St, Christchurch 8014',
'1980-06-01', 'Male', 'Rudolph', '023-444-0000',
'weekly', 0, '2021-04-10', FALSE);

INSERT INTO trainers VALUES (300, 'Blaine', 'Boren',
'blaine@tester.com', '000-111-1111', '56 Howser St, Christchurch 8044', NULL,
'1971-06-17', 'Male', 'Mrs. Clause', '021-111-0000',
'pilates, yoga', FALSE);

INSERT INTO trainers VALUES (444, 'Loraine', 'Bijos',
'loraine@tester.com', '000-111-1111', '4 Kowhai St, Christchurch 8014', NULL,
'1993-08-17', 'Female', 'Santa Clause', '023-888-0000',
'karate, weights', FALSE);

INSERT INTO login VALUES (100, 'rita@tester.com', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'member');
INSERT INTO login VALUES (202, 'sydney@tester.com', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'member');
INSERT INTO login VALUES (300, 'blaine@tester.com', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'trainer');
INSERT INTO login VALUES (444, 'loraine@tester.com', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'trainer');

INSERT INTO payments VALUES (887, '2021-02-01', 45, 'subscription', 100), (888, '2021-03-01', 45, 'subscription', 100), 
(889, '2021-03-03', 15, 'training', 202);

INSERT INTO groupclasses VALUES (700, 'Yoga', 'a meditative morning class', 'Monday', '8:00', 60, 300), 
(701, 'Weight Lifting', 'focus on strength', 'Thursday', '15:00', 60, 444);

INSERT INTO groupsession VALUES (606, '2021-04-19', 0, 700), (610, '2021-04-21', 0, 701);

INSERT INTO training VALUES (432, '2021-04-19', '17:00', NULL, 100, 444), 
(433, '2021-04-20', '13:00', NULL, 202, 300);