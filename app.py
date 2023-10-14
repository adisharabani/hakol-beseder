from flask import Flask, render_template, request, session, redirect, url_for
from myApp import app,twilio_sid, twilio_auth, twilio_number

from twilio.rest import Client
import random

from models import *
from datetime import datetime, timedelta

import logging
 

def getCurrentUser():
    if "user-id" in session:
        return User.query.get(str(session["user-id"]))
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
def repr(user):
    if user.name is None:
        return user.phone_number
    else:
        return f"{user.name} ({user.phone_number})"

@app.template_filter()
def relativeDate(last_seen):
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
    elif time_difference < timedelta(days=30):
        days = time_difference.days
        return f"לפני {days} ימים"
    else:
        return last_seen.strftime("%d/%m/%Y")


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
    elif time_difference < timedelta(days=1):
        hours = int(time_difference.total_seconds() // 3600)
        minutes = int(time_difference.total_seconds() // 60 - hours * 60)
        return f"ב-{hours}:{minutes:02} השעות האחרונות"
    elif time_difference < timedelta(days=30):
        days = time_difference.days
        return f"ב-{days} הימים האחרונים"
    else:
        return "מאז " + last_seen.strftime("%d/%m/%Y")

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
    number = number.replace("-","").replace(" ","")
    if number.startswith("+"):
        if len(number) >= 11 and len(number)<=16:
            return number
    if number.startswith("0"):
        if len(number) == 10 or (not number.startswith("05")) and len(number) == 9:
            return "+972"+number[1:]
    return None

@app.route('/login', methods=["GET","POST"])
def login(pending_group_id = None, pending_friend_id = None):
    phone_number = request.form.get("phone_number")
    verification_code = request.form.get("verification_code")

    pending_group_id = request.args.get("pending_group_id",pending_group_id)
    pending_friend_id = request.args.get("pending_friend_id",pending_friend_id)

    number_e164 = to_e164(phone_number)

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
        number_e164 == session.get("number-e164"):
        #authenticate
        createUser(phone_number)

        del session["verification-code"]
        del session["number-e164"]

        #show group if this came from a group invite
        if pending_friend_id:
            return myRedirect("addFriend", f"id={pending_friend_id}")
        elif pending_group_id:
            return myRedirect("addGroup", f"id={pending_group_id}")
        else:
            return myRedirect("main")

    group = db.session.query(Group).filter_by(id=pending_group_id).first() if pending_group_id else None
    friend = db.session.query(User).filter_by(id=pending_friend_id).first() if pending_friend_id else None

    return render_template("login.html", phone_number=phone_number, verification_code = verification_code, number_e164=number_e164,
                            group = group, friend = friend)
 


@app.route('/', methods=["GET", "POST", "HEAD"])
def main():
    group_id = request.args.get("group_id")
    friend_id = request.args.get("friend_id")

    user = getCurrentUser()
    if user is None: 
        if group_id and friend_id: return myRedirect("login", f"pending_group_id={group_id}&pending_friend_id={friend_id}")
        if group_id: return myRedirect("login", f"pending_group_id={group_id}")
        if friend_id: return myRedirect("login", f"pending_friend_id={friend_id}")
        return myRedirect("login")

    if request.form.get("status"): #TODO: WHAT IS THIS?
        print(request.form.get("status"))

    #group_id = request.args.get("group_id")
    group = db.session.query(Group).filter_by(id=group_id).first() if group_id else None
    friend = db.session.query(User).filter_by(id=friend_id).first() if friend_id else None

    if group and group in user.groups or \
        friend and friend in user.friends and not group:
        return myRedirect("main")


    # show_is_ok = session.get("show_is_ok") or (user.groups or user.friends) and (datetime.utcnow() - user.last_seen).total_seconds() >= 300
    show_is_ok = session.get("show_is_ok") or (datetime.utcnow() - user.last_seen).total_seconds() >= 300
    #TODO: Add group invite screen
    session["show_is_ok"] = False
    return render_template("main.html", 
                            user=user, selected_group=group, selected_friend=friend,
                            show_is_ok = show_is_ok,
                            current_time = datetime.utcnow(), min_datetime=datetime.min)

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
        return myRedirect("login", f"pending_group_id={group_id}")

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
        return myRedirect("login", f"pending_friend_id={friend_id}")

    if friend_id: 
        friend = db.session.query(User).filter_by(id=friend_id).first()
        if friend:
            user.add_friend(friend)
            db.session.add(user)
            db.session.commit()
            print("Friend added")
        else:
            print("Friend not found")
    return myRedirect("main")


@app.route("/recreateDB")
def recreateDB():
    db.drop_all()
    db.create_all()
    return "OK"

@app.route("/createdb")
def createDB():
    # with app.app_context():
    db.create_all()
    return "OK"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001)

