"""
app.py - Flask application for the Smart Hostel Outpass Management System.

Run:  python app.py      then open  http://127.0.0.1:5000
"""
import hashlib
import hmac
import io
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

import qrcode
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash

import database as db
import nlp_processing as nlp

COLLEGE_NAME = "Sri Vidya Institute of Engineering & Technology"
HOSTEL_NAME = "Central Boys & Girls Hostel"

app = Flask(__name__)
# Secret key: from the environment if set, otherwise a random key persisted in
# instance file so sessions survive restarts but no key is hard-coded in source.
_key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secret_key")
if os.environ.get("OUTPASS_SECRET"):
    app.secret_key = os.environ["OUTPASS_SECRET"]
else:
    if not os.path.exists(_key_file):
        with open(_key_file, "w") as f:
            f.write(secrets.token_hex(32))
    app.secret_key = open(_key_file).read().strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=4))


# ------------------------------------------------------------------ helpers
def get_db():
    if "db" not in g:
        g.db = db.get_conn()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def ensure_db():
    if not os.path.exists(db.DB_PATH):
        db.init_db()
    else:
        db.init_db(with_demo=False)  # creates missing tables only


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["COLLEGE_NAME"] = COLLEGE_NAME
app.jinja_env.filters["t12"] = nlp.format_time_12h


@app.template_filter("pretty_date")
def pretty_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d %b %Y (%A)")
    except (TypeError, ValueError):
        return s or "-"


@app.before_request
def protect_post():
    """CSRF protection for every state-changing request."""
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Invalid or missing CSRF token. Please reload the page and try again.")


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store" if request.endpoint not in ("static",) else "public, max-age=3600"
    return resp


def student_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "student":
            flash("Please log in as a student to continue.", "warning")
            return redirect(url_for("student_login"))
        return f(*a, **kw)
    return wrapper


def warden_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "warden":
            if session.get("role") == "student":
                abort(403)
            flash("Warden login required.", "warning")
            return redirect(url_for("warden_login"))
        return f(*a, **kw)
    return wrapper


def sign(outpass_no):
    return hmac.new(app.secret_key.encode(), outpass_no.encode(), hashlib.sha256).hexdigest()[:16]


# -------------------------------------------------------------- validation
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\d{10}$")
ID_RE = re.compile(r"^[A-Za-z0-9\-]{4,20}$")


def validate_registration(f):
    errors = []
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,59}", f.get("name", "").strip()):
        errors.append("Enter a valid full name (letters only).")
    if not ID_RE.match(f.get("student_id", "").strip()):
        errors.append("Student ID must be 4-20 letters/digits (e.g. 21CS001).")
    if not EMAIL_RE.match(f.get("email", "").strip()):
        errors.append("Enter a valid e-mail address.")
    if not PHONE_RE.match(f.get("phone", "").strip()):
        errors.append("Phone number must be exactly 10 digits.")
    if f.get("parent_phone", "").strip() and not PHONE_RE.match(f["parent_phone"].strip()):
        errors.append("Parent phone must be exactly 10 digits.")
    if not f.get("department", "").strip():
        errors.append("Department is required.")
    if f.get("year", "") not in ("1", "2", "3", "4"):
        errors.append("Select a valid year of study.")
    if not f.get("hostel_block", "").strip() or not f.get("room_no", "").strip():
        errors.append("Hostel block and room number are required.")
    pw = f.get("password", "")
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        errors.append("Password must be at least 8 characters with letters and digits.")
    if pw != f.get("confirm_password", ""):
        errors.append("Passwords do not match.")
    return errors


# --------------------------------------------------------------- public pages
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        f = {k: v.strip() for k, v in request.form.items() if k != "_csrf"}
        f["password"] = request.form.get("password", "")          # do not strip passwords
        f["confirm_password"] = request.form.get("confirm_password", "")
        errors = validate_registration(f)
        if not errors:
            try:
                data = dict(f, year=int(f["year"]))
                db.create_student(get_db(), data, f["password"])
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("student_login"))
            except sqlite3.IntegrityError:
                errors.append("A student with this Student ID or e-mail already exists.")
        for e in errors:
            flash(e, "danger")
        f.pop("password", None)
        f.pop("confirm_password", None)
        return render_template("register.html", form=f), 400
    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip()
        pw = request.form.get("password", "")
        s = db.get_student_by_login(get_db(), ident) if ident else None
        if s and check_password_hash(s["password_hash"], pw):
            session.clear()
            session.update(role="student", uid=s["id"], name=s["name"])
            session.permanent = True
            return redirect(url_for("student_dashboard"))
        flash("Invalid Student ID/e-mail or password.", "danger")
        return render_template("login.html"), 401
    return render_template("login.html")


@app.route("/warden/login", methods=["GET", "POST"])
def warden_login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        w = db.get_warden_by_username(get_db(), u) if u else None
        if w and check_password_hash(w["password_hash"], pw):
            session.clear()
            session.update(role="warden", uid=w["id"], name=w["name"])
            session.permanent = True
            return redirect(url_for("warden_dashboard"))
        flash("Invalid warden username or password.", "danger")
        return render_template("warden_login.html"), 401
    return render_template("warden_login.html")


@app.route("/logout", methods=["POST"])
def logout():
    role = session.get("role")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("warden_login") if role == "warden" else url_for("home"))


# ------------------------------------------------------------ student module
@app.route("/student/dashboard")
@student_required
def student_dashboard():
    conn = get_db()
    reqs = db.list_requests(conn, student_pk=session["uid"])
    # newest first for students
    reqs = sorted(reqs, key=lambda r: r["created_at"], reverse=True)
    return render_template("student_dashboard.html", reqs=reqs[:5],
                           stats=db.counts(conn, session["uid"]),
                           student=db.get_student(conn, session["uid"]))


@app.route("/student/profile")
@student_required
def student_profile():
    return render_template("student_profile.html", student=db.get_student(get_db(), session["uid"]))


@app.route("/student/request", methods=["GET", "POST"])
@student_required
def new_request():
    if request.method == "POST":
        text = request.form.get("message", "").strip()
        if len(text) < 10:
            flash("Please describe your request in at least a short sentence (10+ characters).", "danger")
            return render_template("request_form.html", message=text), 400
        if len(text) > 500:
            flash("Request is too long (maximum 500 characters).", "danger")
            return render_template("request_form.html", message=text[:500]), 400
        info = nlp.analyze_request(text)
        if not info["is_valid"]:
            flash("The message is too short to understand. Please add more detail.", "danger")
            return render_template("request_form.html", message=text), 400
        session["analysis"] = info
        return redirect(url_for("analysis_result"))
    return render_template("request_form.html", message="")


@app.route("/student/analysis")
@student_required
def analysis_result():
    info = session.get("analysis")
    if not info:
        flash("Please write a request first.", "warning")
        return redirect(url_for("new_request"))
    return render_template("analysis.html", info=info, today=date.today().isoformat(),
                           max_date=(date.today() + timedelta(days=60)).isoformat())


@app.route("/student/request/confirm", methods=["POST"])
@student_required
def confirm_request():
    info = session.get("analysis")
    if not info:
        flash("Your session expired. Please submit the request again.", "warning")
        return redirect(url_for("new_request"))
    dest = request.form.get("destination", "").strip()
    dep_date = request.form.get("departure_date", "").strip()
    ret_time = request.form.get("return_time", "").strip()
    dep_time = request.form.get("departure_time", "").strip() or None
    category = request.form.get("category", info["category"])
    errors = []
    if not dest or len(dest) > 80:
        errors.append("Destination is required (max 80 characters).")
    try:
        d = datetime.strptime(dep_date, "%Y-%m-%d").date()
        if d < date.today():
            errors.append("Departure date cannot be in the past.")
        elif d > date.today() + timedelta(days=60):
            errors.append("Departure date cannot be more than 60 days ahead.")
    except ValueError:
        errors.append("A valid departure date is required.")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", ret_time):
        errors.append("A valid return time is required.")
    if dep_time and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", dep_time):
        errors.append("Departure time is not valid.")
    if category not in nlp.CATEGORIES:
        errors.append("Invalid category.")
    if not errors and ret_time and dep_time and ret_time <= dep_time:
        errors.append("Return time must be after the departure time (same-day outpass).")
    conn = get_db()
    if not errors and db.find_duplicate(conn, session["uid"], dep_date, ret_time):
        errors.append("You already have a Pending or Approved outpass request for this date.")
    if errors:
        for e in errors:
            flash(e, "danger")
        return render_template("analysis.html", info=info, today=date.today().isoformat(),
                               max_date=(date.today() + timedelta(days=60)).isoformat()), 400
    info = dict(info, destination=dest, departure_date=dep_date, return_time=ret_time,
                departure_time=dep_time, category=category)
    # re-run priority with the confirmed values
    info["priority"], info["priority_reason"] = nlp.suggest_priority(
        info["original_text"], category, d)
    rid = db.create_request(conn, session["uid"], info)
    session.pop("analysis", None)
    flash("Your outpass request has been submitted to the warden.", "success")
    return redirect(url_for("request_detail", rid=rid))


@app.route("/student/requests")
@student_required
def my_requests():
    status = request.args.get("status")
    if status not in (None, "", "Pending", "Approved", "Rejected"):
        status = None
    reqs = db.list_requests(get_db(), student_pk=session["uid"], status=status or None)
    reqs = sorted(reqs, key=lambda r: r["created_at"], reverse=True)
    return render_template("my_requests.html", reqs=reqs, status=status or "")


@app.route("/student/request/<int:rid>")
@student_required
def request_detail(rid):
    conn = get_db()
    r = db.get_request(conn, rid)
    if not r or r["student_pk"] != session["uid"]:
        abort(404)   # do not reveal that other students' requests exist
    import json
    return render_template("request_detail.html", r=r, hist=db.get_history(conn, rid),
                           nlp=json.loads(r["nlp_json"] or "{}"))


@app.route("/student/outpass/<int:rid>")
@student_required
def student_outpass(rid):
    conn = get_db()
    r = db.get_request(conn, rid)
    if not r or r["student_pk"] != session["uid"]:
        abort(404)
    if r["status"] != "Approved":
        abort(403)
    return render_template("outpass.html", r=r, college=COLLEGE_NAME, hostel=HOSTEL_NAME,
                           pdf_url=url_for("outpass_pdf", rid=rid), qr_url=url_for("outpass_qr", rid=rid))


# ----------------------------------------------------- outpass PDF + QR code
def _can_access_outpass(r):
    if session.get("role") == "warden":
        return True
    return session.get("role") == "student" and r["student_pk"] == session.get("uid")


def _verify_url(r):
    base = request.host_url.rstrip("/")
    return "%s/verify/%s/%s" % (base, r["outpass_no"], sign(r["outpass_no"]))


def make_qr_png(text):
    img = qrcode.make(text, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@app.route("/outpass/<int:rid>/qr.png")
def outpass_qr(rid):
    r = db.get_request(get_db(), rid)
    if not r or r["status"] != "Approved" or not _can_access_outpass(r):
        abort(403)
    return send_file(make_qr_png(_verify_url(r)), mimetype="image/png")


def build_pdf(r, verify_url):
    """Render the digital outpass as an A4 PDF with ReportLab. Returns BytesIO."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    navy, teal = colors.HexColor("#1e3a8a"), colors.HexColor("#0d9488")
    c.setTitle("Outpass " + r["outpass_no"])
    # header band
    c.setFillColor(navy)
    c.rect(0, H - 38 * mm, W, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(W / 2, H - 15 * mm, COLLEGE_NAME)
    c.setFont("Helvetica", 11)
    c.drawCentredString(W / 2, H - 22 * mm, HOSTEL_NAME)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, H - 32 * mm, "DIGITAL HOSTEL OUTPASS")
    # id strip
    c.setFillColor(colors.HexColor("#f1f5f9"))
    c.rect(15 * mm, H - 55 * mm, W - 30 * mm, 12 * mm, fill=1, stroke=0)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, H - 50 * mm, "Outpass ID: " + r["outpass_no"])
    c.setFillColor(colors.HexColor("#15803d"))
    c.drawRightString(W - 20 * mm, H - 50 * mm, "STATUS: APPROVED")

    rows = [
        ("Student Name", r["student_name"]),
        ("Student ID", r["roll_no"]),
        ("Department / Year", "%s / Year %s" % (r["department"], r["year"])),
        ("Hostel / Room", "%s, Room %s" % (r["hostel_block"], r["room_no"])),
        ("Reason for Leaving", r["category"]),
        ("Destination", r["destination"]),
        ("Departure Date", pretty_date(r["departure_date"])),
        ("Expected Return Time", nlp.format_time_12h(r["return_time"])),
        ("Priority", r["priority"]),
        ("Approved By", "%s (%s)" % (r["warden_name"], r["warden_designation"])),
        ("Approved On", r["decided_at"]),
        ("Warden Remarks", r["warden_remarks"] or "-"),
    ]
    y = H - 68 * mm
    for i, (k, v) in enumerate(rows):
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#f8fafc"))
            c.rect(15 * mm, y - 3 * mm, W - 30 * mm, 9 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(20 * mm, y, k)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10.5)
        c.drawString(75 * mm, y, str(v)[:70])
        y -= 9 * mm
    # QR
    qr = ImageReader(make_qr_png(verify_url))
    c.drawImage(qr, W - 62 * mm, 62 * mm, 42 * mm, 42 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawCentredString(W - 41 * mm, 57 * mm, "Scan to verify this outpass")
    # signature block
    c.setStrokeColor(colors.HexColor("#94a3b8"))
    c.line(20 * mm, 75 * mm, 80 * mm, 75 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawString(20 * mm, 70 * mm, r["warden_name"])
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, 65 * mm, r["warden_designation"])
    # rules
    c.setFillColor(teal)
    c.rect(15 * mm, 18 * mm, W - 30 * mm, 28 * mm, fill=0, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, 41 * mm, "Instructions")
    c.setFont("Helvetica", 8.5)
    for i, line in enumerate([
        "1. Show this outpass (printed or on phone) to the security guard at the gate.",
        "2. Return to the hostel before the expected return time mentioned above.",
        "3. This outpass is valid only for the date and destination stated.",
        "4. Misuse or late return may lead to disciplinary action."]):
        c.drawString(18 * mm, 36 * mm - i * 5 * mm, line)
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(W / 2, 11 * mm, "Computer-generated document. Verification link: " + verify_url[:90])
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


@app.route("/outpass/<int:rid>/pdf")
def outpass_pdf(rid):
    r = db.get_request(get_db(), rid)
    if not r or not _can_access_outpass(r):
        abort(403)
    if r["status"] != "Approved":
        abort(403)
    return send_file(build_pdf(r, _verify_url(r)), mimetype="application/pdf",
                     as_attachment=True, download_name="Outpass_%s.pdf" % r["outpass_no"])


@app.route("/verify/<outpass_no>/<sig>")
def verify(outpass_no, sig):
    """Public page opened by scanning the QR code (gate security)."""
    row = get_db().execute("SELECT id FROM outpass_requests WHERE outpass_no=? AND status='Approved'",
                           (outpass_no,)).fetchone()
    valid = bool(row) and hmac.compare_digest(sig, sign(outpass_no))
    r = db.get_request(get_db(), row["id"]) if valid else None
    return render_template("verify.html", r=r, valid=valid,
                           today=date.today().isoformat()), (200 if valid else 404)


# ------------------------------------------------------------- warden module
@app.route("/warden/dashboard")
@warden_required
def warden_dashboard():
    conn = get_db()
    status = request.args.get("status", "")
    if status not in ("Pending", "Approved", "Rejected"):
        status = ""
    prio = request.args.get("priority", "")
    reqs = db.list_requests(conn, status=status or None)
    if prio in ("High", "Medium", "Low"):
        reqs = [r for r in reqs if r["priority"] == prio]
    q = request.args.get("q", "").strip().lower()
    if q:
        reqs = [r for r in reqs if q in r["student_name"].lower() or q in r["roll_no"].lower()
                or q in r["destination"].lower()]
    return render_template("warden_dashboard.html", reqs=reqs, stats=db.counts(conn),
                           status=status, prio=prio, q=q)


@app.route("/warden/request/<int:rid>")
@warden_required
def review_request(rid):
    import json
    conn = get_db()
    r = db.get_request(conn, rid)
    if not r:
        abort(404)
    past = db.list_requests(conn, student_pk=r["student_pk"])
    past = [p for p in past if p["id"] != rid]
    return render_template("review.html", r=r, hist=db.get_history(conn, rid),
                           nlp=json.loads(r["nlp_json"] or "{}"), past=past)


@app.route("/warden/request/<int:rid>/decide", methods=["POST"])
@warden_required
def decide(rid):
    decision = request.form.get("decision")
    remarks = request.form.get("remarks", "").strip()[:300]
    if decision not in ("Approved", "Rejected"):
        abort(400, "Invalid decision.")
    if decision == "Rejected" and len(remarks) < 3:
        flash("Please add a remark explaining the reason for rejection.", "danger")
        return redirect(url_for("review_request", rid=rid))
    ok = db.decide_request(get_db(), rid, session["uid"], decision, remarks or None)
    if not ok:
        flash("This request has already been decided or does not exist.", "warning")
    else:
        flash("Request %s successfully." % decision.lower(), "success")
    return redirect(url_for("review_request", rid=rid))


@app.route("/warden/outpass/<int:rid>")
@warden_required
def warden_outpass(rid):
    r = db.get_request(get_db(), rid)
    if not r:
        abort(404)
    if r["status"] != "Approved":
        flash("Outpass is generated only after approval.", "warning")
        return redirect(url_for("review_request", rid=rid))
    return render_template("outpass.html", r=r, college=COLLEGE_NAME, hostel=HOSTEL_NAME,
                           pdf_url=url_for("outpass_pdf", rid=rid), qr_url=url_for("outpass_qr", rid=rid))


# ----------------------------------------------------------- error handlers
@app.errorhandler(400)
def e400(e):
    return render_template("error.html", code=400, title="Bad Request",
                           msg=getattr(e, "description", "")), 400


@app.errorhandler(403)
def e403(e):
    return render_template("error.html", code=403, title="Access Denied",
                           msg="You do not have permission to open this page."), 403


@app.errorhandler(404)
def e404(e):
    return render_template("error.html", code=404, title="Not Found",
                           msg="The page or record you asked for does not exist."), 404


ensure_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
