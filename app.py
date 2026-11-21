import os, json, sqlite3, secrets
from datetime import datetime
from functools import wraps
from io import BytesIO
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash

import os
import json
import secrets

from flask import Flask, request, session, redirect, url_for, flash, render_template
from dotenv import load_dotenv

# Project directory
BASE = os.path.dirname(os.path.abspath(__file__))

# Load .env from the same folder as app.py
load_dotenv(os.path.join(BASE, ".env"), override=True)

# Database
DB = os.path.join(BASE, "instance", "exam.db")

# Load questions
with open(os.path.join(BASE, "data", "questions.json"),
          encoding="utf-8") as f:
    QUESTIONS = json.load(f)

# Flask application
app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "smec@123")

app.config["CODE"] = os.getenv(
    "EXAM_VERIFICATION_CODE", "smec@2026"
)

app.config["ADMIN_USER"] = os.getenv(
    "ADMIN_USER", "admin"
)

app.config["ADMIN_PASS"] = os.getenv(
    "ADMIN_PASS", "Admin@123"
)
print("Admin username:", repr(app.config["ADMIN_USER"]))
print("Admin password loaded:", bool(app.config["ADMIN_PASS"]))
os.makedirs(os.path.dirname(DB), exist_ok=True)

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT,
            password_hash TEXT NOT NULL, registered_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER UNIQUE NOT NULL,
            score INTEGER NOT NULL, total INTEGER NOT NULL, submitted_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id))""")

def student_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("student_id"): return redirect(url_for("login"))
        return fn(*a, **k)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return fn(*a, **k)
    return w

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("full_name","").strip()
        user=request.form.get("username","").strip()
        email=request.form.get("email","").strip().lower()
        phone=request.form.get("phone","").strip()
        pw=request.form.get("password","")
        if not all([name,user,email,pw]):
            flash("Please complete all required fields.","danger")
        elif len(pw)<8:
            flash("Password must contain at least 8 characters.","danger")
        else:
            try:
                with db() as c:
                    c.execute("INSERT INTO students(username,full_name,email,phone,password_hash,registered_at) VALUES(?,?,?,?,?,?)",
                    (user,name,email,phone,generate_password_hash(pw),datetime.now().isoformat(timespec="seconds")))
                flash("Registration successful. Please log in.","success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.","danger")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        with db() as c:
            s=c.execute("SELECT * FROM students WHERE username=?",(request.form.get("username","").strip(),)).fetchone()
        if s and check_password_hash(s["password_hash"],request.form.get("password","")):
            session.clear()
            session["student_id"]=s["id"]; session["username"]=s["username"]; session["verified"]=False
            return redirect(url_for("verify"))
        flash("Invalid username or password.","danger")
    return render_template("login.html")

@app.route("/verify", methods=["GET","POST"])
@student_required
def verify():
    if request.method=="POST":
        code=request.form.get("code","")
        if secrets.compare_digest(code,app.config["CODE"]):
            session["verified"]=True
            return redirect(url_for("exam"))
        flash("Incorrect verification code.","danger")
    return render_template("verify.html")

@app.route("/exam", methods=["GET","POST"])
@student_required
def exam():
    if not session.get("verified"): return redirect(url_for("verify"))
    with db() as c:
        done=c.execute("SELECT 1 FROM results WHERE student_id=?",(session["student_id"],)).fetchone()
    if done: return redirect(url_for("result"))
    if request.method=="POST":
        score=sum(1 for q in QUESTIONS if request.form.get("q"+str(q["id"]))==q["answer"])
        with db() as c:
            try:
                c.execute("INSERT INTO results(student_id,score,total,submitted_at) VALUES(?,?,?,?)",
                (session["student_id"],score,len(QUESTIONS),datetime.now().isoformat(timespec="seconds")))
            except sqlite3.IntegrityError: pass
        return redirect(url_for("result"))
    public=[{"id":q["id"],"question":q["question"],"options":q["options"]} for q in QUESTIONS]
    return render_template("exam.html",questions=public)

@app.route("/result")
@student_required
def result():
    with db() as c:
        r=c.execute("SELECT score,total,submitted_at FROM results WHERE student_id=?",(session["student_id"],)).fetchone()
    if not r: return redirect(url_for("exam"))
    return render_template("result.html",r=r,pct=round(100*r["score"]/r["total"],2))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        u=request.form.get("username",""); p=request.form.get("password","")
        if secrets.compare_digest(u,app.config["ADMIN_USER"]) and secrets.compare_digest(p,app.config["ADMIN_PASS"]):
            session.clear(); session["admin"]=True
            return redirect(url_for("dashboard"))
        flash("Invalid admin login.","danger")
    return render_template("admin_login.html")

@app.route("/admin")
@admin_required
def dashboard():
    with db() as c:
        sc=c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        rc=c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        rows=c.execute("SELECT s.username,s.full_name,r.score,r.total,r.submitted_at FROM results r JOIN students s ON s.id=r.student_id ORDER BY r.submitted_at DESC").fetchall()
    return render_template("admin.html",sc=sc,rc=rc,rows=rows)

def excel(df, filename):
    b=BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w: df.to_excel(w,index=False)
    b.seek(0)
    return send_file(b,as_attachment=True,download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/admin/students.xlsx")
@admin_required
def students_excel():
    with db() as c: rows=c.execute("SELECT username,full_name,email,phone,registered_at FROM students ORDER BY registered_at").fetchall()
    return excel(pd.DataFrame([dict(x) for x in rows],columns=["username","full_name","email","phone","registered_at"]),"registered_students.xlsx")

@app.route("/admin/results.xlsx")
@admin_required
def results_excel():
    with db() as c:
        rows=c.execute("""SELECT s.username,s.full_name,s.email,r.score,r.total,
        ROUND(r.score*100.0/r.total,2) AS percentage,r.submitted_at
        FROM results r JOIN students s ON s.id=r.student_id ORDER BY r.submitted_at""").fetchall()
    return excel(pd.DataFrame([dict(x) for x in rows],columns=["username","full_name","email","score","total","percentage","submitted_at"]),"numpy_exam_results.xlsx")

@app.route("/admin/logout")
def admin_logout():
    session.clear(); return redirect(url_for("admin_login"))

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=os.getenv("FLASK_DEBUG")=="1")
