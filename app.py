from flask import Flask, render_template, request, session, redirect, url_for
from models import *
from myApp import app

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
        return redirect(f"{url}?query")
    else:
        return redirect(url)


@app.route("/test")
def test():
    return "TEST"

@app.route("/logout")
def logout():
    if ("user-id" in session):
        del session["user-id"]
    return myRedirect("login")
 

@app.route('/login', methods=["GET","POST"])
def login():
    phone_number = request.form.get("phone_number")
    print(f"phone_number {phone_number}")
    verification_code = request.form.get("verification_code")
    print(f"verification_code {verification_code}")

    if phone_number and "verification-code" not in session or request.form.get("resend_verification_code"):
        #Invent Verification Code
        session["verification-code"] = "123456"
        #TODO: Send verification code

    if verification_code and verification_code == session.get("verification-code"):
        #authenticate
        createUser(phone_number)
        #show group if this came from a group invite
        if "pending-group-id" in session:
            group_id = session["pending-group-id"]
            del session["pending-group-id"]
            return myRedirect("group", f"id={group_id}")
        else:
            return myRedirect("main")

    return render_template("login.html", phone_number=phone_number, verification_code = verification_code)
 

@app.route('/')
def main():
    user = getCurrentUser()
    if user is None: return login()

    #TODO: Add group invite screen
    return render_template("main.html", user=user)

@app.route('/group')
def group():
    group_id = request.args.get("id") or session.get("pending-group-id")
    user = getCurrentUser()
    if user is None: 
        session["pending-group-id"] = group_id
        return login()

    group = Group.query.get(group_id)
    return render_template("group.html",user=user, group=group)

@app.route("/group/add")
def groupAdd():
    user = getCurrentUser()
    if user is None: 
        return login()

    group = Group()
    group.owner = user
    group.users.append(user)
    db.session.add(group)
    db.session.commit()
    return myRedirect("group", f"id={group.id}")

if __name__ == '__main__':
    app.run()

