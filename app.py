from flask import Flask, render_template, request, session, redirect, url_for
from myApp import app,twilio_sid, twilio_auth, twilio_number,gpt_engine, gpt_api_key

from twilio.rest import Client
import random

from models import *
from datetime import datetime, timedelta

import logging
import phonenumbers
import openai
import re


def getCurrentUser():
    if "user-id" in session:
        return User.query.get(str(session.get("user-id")))
    return None

def createUser(phone_number):
    user = User.query.filter_by(phone_number=phone_number).first()
    if user:
        session["user-id"] = user.id
        session.permanent = True
        return user
    user = User(phone_number = phone_number)
    db.session.add(user)
    db.session.commit()
    session["user-id"] = user.id
    session.permanent = True
    return user

def myRedirect(endpoint, query=None):
    url = url_for(endpoint)
    if url.startswith("http:") and not url.startswith("http://localhost") and not url.startswith("http://1") and not url.startswith("http://imac"):
        url = url.replace("http:","https:")
    if query:
        return redirect(f"{url}?{query}")
    else:
        return redirect(url)

@app.template_filter()
def userToString(user):
    if user.name is None:
        return from_e164(user.phone_number)
    else:
        return f"{user.name} ({from_e164(user.phone_number)})"

@app.template_filter()
def relativeDate(last_seen):
    if last_seen == datetime.min:
        return "עדיין לא התחבר/ה"
    now = datetime.utcnow()  # Assuming last_seen is in UTC time
    time_difference = now - last_seen

    if time_difference < timedelta(minutes=1):
        return "ממש עכשיו"
    elif time_difference < timedelta(hours=1):
        minutes = time_difference.total_seconds() // 60
        return f"לפני {int(minutes)} דקות"
    elif time_difference < timedelta(days=1):
        hours = time_difference.total_seconds() // 3600
        minutes = time_difference.total_seconds() // 60 - hours * 60
        return f"לפני {int(hours)} שעות ו-{int(minutes % 60)} דקות"
    # elif time_difference < timedelta(days=30):
    #     days = time_difference.days
    #     if days==1:
    #         return "אתמול"
    #     return f"לפני {days} ימים"
    else:
        return last_seen.strftime("%d/%m/%Y %H:%M")


@app.template_filter()
def fromRelativeDate(last_seen):
    now = datetime.utcnow()  # Assuming last_seen is in UTC time
    time_difference = now - last_seen

    if time_difference < timedelta(minutes=1):
        return "ממש עכשיו"
    elif time_difference < timedelta(hours=1):
        minutes = int(time_difference.total_seconds() // 60)
        if minutes == 1:
            return f"בדקה האחרונה"
        return f"ב-{minutes} הדקות האחרונות"
    elif time_difference < timedelta(hours=30):
        hours = int(time_difference.total_seconds() // 3600)
        minutes = int(time_difference.total_seconds() // 60 - hours * 60)
        return f"ב-{hours}:{minutes:02} השעות האחרונות"
    elif time_difference < timedelta(days=30):
        days = time_difference.days
        if days==1:
            return f"ביומיים האחרונים"
        return f"ב-{days+1} הימים האחרונים"
    else:
        return "מאז " + last_seen.strftime("%d/%m/%Y %H:%M")

@app.before_request
def enforce_https_and_naked_domain():
    if request.url.startswith("http://127") or request.url.startswith("http://imac"):
        return

    # Check for "www" and redirect to naked domain
    if request.url.startswith('https://www.'):
        url = request.url.replace('https://www.', 'https://', 1)
        code = 301
        return redirect(url, code=code)

    # Check for "www" and redirect to naked domain
    if request.url.startswith('http://www.'):
        url = request.url.replace('http://www.', 'https://', 1)
        code = 301
        return redirect(url, code=code)

    # Check for HTTP and redirect to HTTPS
    if request.url.startswith('http://'):
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)


@app.route("/test")
def test():
    return "TEST"

@app.route("/logout")
def logout():
    if ("user-id" in session):
        del session["user-id"]
    return myRedirect("login")
 
def to_e164(number):
    if not number:
        return None
    number = ''.join([char for char in number if char.isdigit() or char == '+'])
    if number.startswith('+'):
        if len(number) >= 11 and len(number)<=16:
            return number
    if number.startswith('0'):
        if len(number) == 10 or (not number.startswith("05")) and len(number) == 9:
            return "+972"+number[1:]
    return None

def from_e164(e164_number):
    try:
        # Parse the number without specifying a region (letting it infer the region from the number)
        number = phonenumbers.parse(e164_number)
        # Check if the parsed number is valid
        if not phonenumbers.is_valid_number(number):
            return e164_number
        # If it's an Israeli number, format it in the national format
        if number.country_code == 972:  # 972 is the country code for Israel
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL)
        # If it's not an Israeli number, format it in the international format but with dashes
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return e164_number


@app.route('/login', methods=["GET","POST"])
def login():
    phone_number = request.form.get("phone_number")
    verification_code = request.form.get("verification_code")

    group_id = request.args.get("group_id")
    friend_id = request.args.get("friend_id")

    number_e164 = to_e164(phone_number)
    print(repr(number_e164), repr(phone_number))

    if (number_e164 and not verification_code) or request.form.get("resend_verification_code"):
        #Invent Verification Code
        rand = str(random.randint(100000, 999999))

        session["verification-code"] = rand
        session["number-e164"] = number_e164

        twilio_client = Client(twilio_sid, twilio_auth)
        message_body = f"{rand} הוא קוד האימות שלך להתחברות למערכת הכל בסדר"
        message = twilio_client.messages.create(from_=twilio_number, to=number_e164, body=message_body)
        #TODO: Send verification code

    elif verification_code and \
        verification_code == session.get("verification-code") and \
        number_e164 == session.get("number-e164"):# or (phone_number=="#" and verification_code):
        #authenticate
        createUser(number_e164)

        if "verification-code" in session:
            del session["verification-code"]
        if "number-e164" in session:
            del session["number-e164"]

        return myRedirect("main", request.query_string.decode("utf-8"))

    group = db.session.query(Group).filter_by(id=group_id).first() if group_id else None
    friend = db.session.query(User).filter_by(id=friend_id).first() if friend_id else None

    return render_template("login.html", phone_number=phone_number, verification_code = verification_code, number_e164=number_e164,
                            group = group, friend = friend)
 


@app.route('/', methods=["GET", "POST", "HEAD"])
def main():
    group_id = request.args.get("group_id")
    friend_id = request.args.get("friend_id")

    user = getCurrentUser()
    if user is None: 
        # if group_id and friend_id: return myRedirect("login", f"pending_group_id={group_id}&pending_friend_id={friend_id}")
        # if group_id: return myRedirect("login", f"pending_group_id={group_id}")
        # if friend_id: return myRedirect("login", f"pending_friend_id={friend_id}")
        return myRedirect("login", request.query_string.decode("utf-8"))

    if request.form.get("status"): #TODO: WHAT IS THIS?
        print(request.form.get("status"))

    #group_id = request.args.get("group_id")
    group = db.session.query(Group).filter_by(id=group_id).first() if group_id else None
    friend = db.session.query(User).filter_by(id=friend_id).first() if friend_id else None

    #remove unecesary query
    if group and group in user.groups or \
        friend and friend in user.friends and not group:
        return myRedirect("main")

    # show_is_ok = session.get("show_is_ok") or (user.groups or user.friends) and (datetime.utcnow() - user.last_seen).total_seconds() >= 300
    show_is_ok = session.get("show_is_ok") or (datetime.utcnow() - user.last_seen).total_seconds() >= 300
    #TODO: Add group invite screen
    session["show_is_ok"] = False

    isAdmin = "admin" in request.args and user.phone_number == "+972544218000"
    return render_template("main.html", 
                            user=user, selected_group=group, selected_friend=friend,
                            show_is_ok = show_is_ok, 
                                groups = user.groups if not isAdmin else Group.query.all(),
                                friends = user.friends if not isAdmin else User.query.all(),
                            isAdmin = isAdmin)

@app.route('/analyzeContacts', methods=['POST'])
def analyzeContacts():
    # contacts = request.form.get("contacts")
    # print(contacts)
    # if contacts:
    #     show_is_ok = False
    #     if contactsValid(contacts):
    #         contactsImport(contacts)
    #     else:
    #         contacts = contactsAnalyze(contacts)
    #         print("EDIT")
    #         print(contacts)
    #         print("DONE")
    try:
        contacts = request.data.decode('utf-8')
        if not contacts.strip():
            return contacts
        # response = openai.Completion.create(
        #     engine=gpt_engine,  # You can choose the appropriate engine
        #     prompt="extract the all phone numbers from the following text and put each in a separate line. Convert phone number to e164 format (some might be in Israel local format). If there is a name next to the number put the name in the line of the number with one comma between the number and the name. Do your best effort, but only respond with this format:\n\n" + contacts,
        #     max_tokens=1000,  # Adjust max tokens as needed
        #     api_key=gpt_api_key
        # )
        # print(response)
        # return response.choices[0].text.strip()
        openai.api_key = gpt_api_key
        response = openai.ChatCompletion.create( 
            model=gpt_engine, 
            messages=[{"role":"system","content":"You will receive a text and required to extract the all phone numbers and put each in a separate line. Convert phone number to e164 format (some might be in Israel local format). If there is a name next to the number put the name in the line of the number with one comma between the number and the name. Do your best effort"},
                      {"role":"user", "content":contacts}], 
            max_tokens = 2000, 
            temperature=0) 
        # print(response)
        return response.choices[0].message.content
    except Exception as e:
        return str(e), 400

pattern = r'^\+\d{1,15},\s*.*$'
def contactsValid(contacts):
    lines = contacts.split('\n')
    for line in lines:
        if not re.match(pattern, line):
            return False
    return True

@app.route("/group/import", methods=["POST"])
def contactsImport():
    user = getCurrentUser()
    contacts = request.form.get("contacts")
    groupId = request.form.get("group_id")

    if user is None or groupId is None:
        return myRedirect("login")

    group = db.session.query(Group).filter_by(id=groupId).first()
    if group is None:
        print("group not found")
        return myRedirect("login")

    if user not in group.users:
        print("Bad User")
        return myRedirect("main")
    users = []
    for line in contacts.split("\n"):
        s = line.split(",")
        phone_number,name = to_e164(s[0]), ",".join(s[1:]).strip()
        print (f"Trying to add {phone_number}, {name} ")
        # check if user exists
        if phone_number:
            u = User.query.filter_by(phone_number=phone_number).first()
            if not u:
                u = User(phone_number = phone_number, name = name or None)
            users.append(u)
        # create user
        # add to group
    if users:
        for u in users:
            db.session.add(u)
            if u not in group.users:
                group.users.append(u)
        db.session.add(group)
        db.session.commit()

    return myRedirect("main")

@app.route('/is_ok')
def is_ok():
    user = getCurrentUser()
    if user is None: return myRedirect("login")
    session["show_is_ok"] = True
    return myRedirect("main")

@app.route("/group/add")
def addGroup():
    group = None
    group_id = request.args.get("id")

    user = getCurrentUser()
    if user is None:
        return myRedirect("login", f"group_id={group_id}")

    if group_id:
        group = db.session.query(Group).filter_by(id=group_id).first()

    if not group:
        group = Group()
        group.owner = user

    group.users.append(user)
    db.session.add(group)
    db.session.commit()
    return myRedirect("main")#, f"group_id={group.id}")

@app.route("/group/update", methods=['POST'])
def updateGroup():
    user = getCurrentUser()
    if user is None:
        return "User not found"

    group_id = request.json.get("id")
    name = request.json.get("name")
    leave = request.json.get("leave")

    if group_id is None:
        return "No group provided"

    group = db.session.query(Group).filter_by(id=group_id).first()
    if group is None:
        return "Group not found"
    if name is not None:
        group.name = name
        db.session.add(group)
        db.session.commit()
        return "OK"
    elif leave and user in group.users:
        if len(group.users) == 1:
            db.session.delete(group)
        else:
            group.users.remove(user)
            db.session.add(group)
        db.session.commit()
        return "OK"
    else:
        return "incomplete input"

@app.route("/status/update", methods=['POST'])
def updateStatus():
    user = getCurrentUser()
    if user is None:
        return "User not found"

    name = request.json.get("name")
    is_ok = request.json.get("is_ok")
    didChange = False
    if name is not None:
        user.name = name
        didChange = True
    if is_ok is not None:
        user.is_ok = is_ok
        user.prev_seen = user.last_seen
        user.last_seen = datetime.utcnow()
        didChange = True
    if didChange:
        db.session.add(user)
        db.session.commit()
        return "OK"
    else:
        return "invalid input"

@app.route("/friend/add")
def addFriend():
    friend_id = request.args.get("id")

    user = getCurrentUser()
    if user is None: 
        return myRedirect("login", f"friend_id={friend_id}")

    if friend_id: 
        friend = db.session.query(User).filter_by(id=friend_id).first()
        if friend:
            user.add_friend(friend)
            db.session.add(user)
            db.session.commit()
            # print("Friend added")
        else:
            pass
            # print("Friend not found")
    return myRedirect("main")

@app.route("/friend/remove", methods=["GET","POST"])
def removeFriend():
    friend_id = request.json.get("id")
    user = getCurrentUser()
    if user is None: 
        return myRedirect("login")

    if friend_id: 
        friend = db.session.query(User).filter_by(id=friend_id).first()
        if friend:
            if user in friend.my_friends:
                friend.my_friends.remove(user)
                db.session.add(friend)
            if friend in user.my_friends:
                user.my_friends.remove(friend)
                db.session.add(user)
            db.session.commit()
            return "OK"
        else:
            return "Friend not found"
    return "invalid input"


# @app.route("/recreateDB")
# def recreateDB():
#     db.drop_all()
#     db.create_all()
#     return "OK"

# @app.route("/createdb")
# def createDB():
#     # with app.app_context():
#     db.create_all()
#     return "OK"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001)

