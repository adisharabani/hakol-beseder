from flask import Flask, render_template, request, session, redirect, url_for
from myApp import app
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
        return user
    user = User(phone_number = phone_number)
    db.session.add(user)
    db.session.commit()
    session["user-id"] = user.id
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
 

@app.route('/login', methods=["GET","POST"])
def login(pending_group_id = None, pending_friend_id = None):
    phone_number = request.form.get("phone_number")
    verification_code = request.form.get("verification_code")

    pending_group_id = request.form.get("pending_group_id",pending_group_id)
    pending_friend_id = request.form.get("pending_friend_id",pending_friend_id)

    if phone_number and "verification-code" not in session or request.form.get("resend_verification_code"):
        #Invent Verification Code
        session["verification-code"] = "123456"
        #TODO: Send verification code

    if verification_code and verification_code == session.get("verification-code"):
        #authenticate
        createUser(phone_number)
        #show group if this came from a group invite
        if pending_friend_id:
            return myRedirect("addFriend", f"id={pending_friend_id}")
        elif pending_group_id:
            return myRedirect("group", f"id={pending_group_id}")
        else:
            return myRedirect("main")

    return render_template("login.html", phone_number=phone_number, verification_code = verification_code, pending_group_id = pending_group_id)
 

@app.route('/', methods=["GET", "POST"])
def main():
    group_id = request.args.get("group_id")
    user = getCurrentUser()
    if user is None: return myRedirect("login", f"pending_group_id={group_id}" if group_id else None)

    if request.form.get("status"):
        print(request.form.get("status"))

    group_id = request.args.get("group_id")
    group = db.session.query(Group).filter_by(id=group_id).first() if group_id else None

    #TODO: Add group invite screen
    return render_template("main.html", user=user, selected_group=group, current_time = datetime.utcnow(), min_datetime=datetime.min)

@app.route('/is_ok')
def is_ok():
    user = getCurrentUser()
    if user is None: return myRedirect("login")

    return render_template("is_ok.html", user=user)

@app.route("/group/add")
def addGroup():
    group = None
    group_id = request.args.get("id")

    user = getCurrentUser()
    if user is None:
        return myRedirect("login")

    if group_id:
        group = db.session.query(Group).filter_by(id=group_id).first()
    if not group:
        group = Group()
        group.owner = user

    group.users.append(user)
    db.session.add(group)
    db.session.commit()
    return myRedirect("main", f"group_id={group.id}")

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

