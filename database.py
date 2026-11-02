"""
database.py - SQLite schema + helper functions.

All queries use parameter placeholders (?) so user input is never pasted into
SQL text (protects against SQL injection).

Run  `python database.py`  to create the database and demo data
(also available as `python init_db.py`).
"""
import json
import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("OUTPASS_DB", os.path.join(BASE_DIR, "outpass.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL UNIQUE,          -- roll / register number
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT NOT NULL,
    department    TEXT NOT NULL,
    year          INTEGER NOT NULL,
    hostel_block  TEXT NOT NULL,
    room_no       TEXT NOT NULL,
    parent_phone  TEXT,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS wardens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    designation   TEXT NOT NULL DEFAULT 'Hostel Warden',
    phone         TEXT,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS outpass_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    outpass_no       TEXT UNIQUE,                -- filled when approved
    student_pk       INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    original_text    TEXT NOT NULL,
    category         TEXT NOT NULL,
    confidence       REAL,
    destination      TEXT NOT NULL,
    departure_date   TEXT NOT NULL,              -- YYYY-MM-DD
    departure_time   TEXT,                       -- HH:MM (optional)
    return_time      TEXT NOT NULL,              -- HH:MM
    priority         TEXT NOT NULL CHECK (priority IN ('High','Medium','Low')),
    nlp_json         TEXT,                       -- full NLP analysis (JSON)
    status           TEXT NOT NULL DEFAULT 'Pending'
                     CHECK (status IN ('Pending','Approved','Rejected')),
    warden_pk        INTEGER REFERENCES wardens(id),
    warden_remarks   TEXT,
    decided_at       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_req_student ON outpass_requests(student_pk);
CREATE INDEX IF NOT EXISTS idx_req_status  ON outpass_requests(status);

CREATE TABLE IF NOT EXISTS approval_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES outpass_requests(id) ON DELETE CASCADE,
    action      TEXT NOT NULL,                   -- Submitted / Approved / Rejected
    actor_role  TEXT NOT NULL,                   -- student / warden
    actor_name  TEXT NOT NULL,
    remarks     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_hist_req ON approval_history(request_id);
"""


def get_conn(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=None, with_demo=True):
    conn = get_conn(path)
    conn.executescript(SCHEMA)
    if with_demo:
        seed_demo_data(conn)
    conn.commit()
    conn.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ users
def create_student(conn, data, password):
    cur = conn.execute(
        """INSERT INTO students (student_id,name,email,phone,department,year,
           hostel_block,room_no,parent_phone,password_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (data["student_id"], data["name"], data["email"], data["phone"],
         data["department"], data["year"], data["hostel_block"], data["room_no"],
         data.get("parent_phone"), generate_password_hash(password)))
    conn.commit()
    return cur.lastrowid


def get_student_by_login(conn, ident):
    """Login by student ID or e-mail."""
    return conn.execute(
        "SELECT * FROM students WHERE lower(student_id)=lower(?) OR lower(email)=lower(?)",
        (ident, ident)).fetchone()


def get_student(conn, pk):
    return conn.execute("SELECT * FROM students WHERE id=?", (pk,)).fetchone()


def get_warden_by_username(conn, username):
    return conn.execute("SELECT * FROM wardens WHERE lower(username)=lower(?)", (username,)).fetchone()


def get_warden(conn, pk):
    return conn.execute("SELECT * FROM wardens WHERE id=?", (pk,)).fetchone()


# --------------------------------------------------------------- requests
def create_request(conn, student_pk, info):
    cur = conn.execute(
        """INSERT INTO outpass_requests
           (student_pk,original_text,category,confidence,destination,departure_date,
            departure_time,return_time,priority,nlp_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (student_pk, info["original_text"], info["category"], info.get("confidence"),
         info["destination"], info["departure_date"], info.get("departure_time"),
         info["return_time"], info["priority"], json.dumps(info)))
    rid = cur.lastrowid
    student = get_student(conn, student_pk)
    add_history(conn, rid, "Submitted", "student", student["name"], "Request submitted")
    conn.commit()
    return rid


def add_history(conn, request_id, action, role, actor, remarks=None):
    conn.execute(
        "INSERT INTO approval_history (request_id,action,actor_role,actor_name,remarks) VALUES (?,?,?,?,?)",
        (request_id, action, role, actor, remarks))


def find_duplicate(conn, student_pk, departure_date, return_time):
    """A duplicate = same student, same date, and an existing Pending/Approved request."""
    return conn.execute(
        """SELECT id FROM outpass_requests
           WHERE student_pk=? AND departure_date=? AND status IN ('Pending','Approved')""",
        (student_pk, departure_date)).fetchone()


def get_request(conn, rid):
    return conn.execute(
        """SELECT r.*, s.name AS student_name, s.student_id AS roll_no, s.department,
                  s.year, s.hostel_block, s.room_no, s.phone, s.parent_phone, s.email,
                  w.name AS warden_name, w.designation AS warden_designation
           FROM outpass_requests r
           JOIN students s ON s.id = r.student_pk
           LEFT JOIN wardens w ON w.id = r.warden_pk
           WHERE r.id=?""", (rid,)).fetchone()


def list_requests(conn, student_pk=None, status=None):
    q = """SELECT r.*, s.name AS student_name, s.student_id AS roll_no, s.department,
                  s.hostel_block, s.room_no
           FROM outpass_requests r JOIN students s ON s.id = r.student_pk WHERE 1=1"""
    args = []
    if student_pk is not None:
        q += " AND r.student_pk=?"
        args.append(student_pk)
    if status:
        q += " AND r.status=?"
        args.append(status)
    q += """ ORDER BY CASE r.status WHEN 'Pending' THEN 0 ELSE 1 END,
                      CASE r.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                      r.created_at DESC"""
    return conn.execute(q, args).fetchall()


def decide_request(conn, rid, warden_pk, decision, remarks):
    """Approve/Reject a Pending request. Returns False if it was not Pending."""
    row = conn.execute("SELECT status FROM outpass_requests WHERE id=?", (rid,)).fetchone()
    if not row or row["status"] != "Pending":
        return False
    warden = get_warden(conn, warden_pk)
    outpass_no = None
    if decision == "Approved":
        outpass_no = "OP%s-%04d" % (datetime.now().strftime("%Y%m%d"), rid)
    conn.execute(
        """UPDATE outpass_requests SET status=?, warden_pk=?, warden_remarks=?,
           decided_at=?, outpass_no=? WHERE id=? AND status='Pending'""",
        (decision, warden_pk, remarks, now(), outpass_no, rid))
    add_history(conn, rid, decision, "warden", warden["name"], remarks)
    conn.commit()
    return True


def get_history(conn, rid):
    return conn.execute(
        "SELECT * FROM approval_history WHERE request_id=? ORDER BY id", (rid,)).fetchall()


def counts(conn, student_pk=None):
    q = "SELECT status, COUNT(*) c FROM outpass_requests"
    args = []
    if student_pk is not None:
        q += " WHERE student_pk=?"
        args.append(student_pk)
    q += " GROUP BY status"
    out = {"Pending": 0, "Approved": 0, "Rejected": 0}
    for r in conn.execute(q, args):
        out[r["status"]] = r["c"]
    out["Total"] = sum(out.values())
    return out


# ------------------------------------------------------------- demo data
DEMO_WARDEN = {"username": "warden", "password": "Warden@123", "name": "Dr. R. Meenakshi",
               "designation": "Chief Hostel Warden", "phone": "9876500001"}
DEMO_STUDENT = {"student_id": "21CS001", "password": "Student@123", "name": "Arun Kumar",
                "email": "arun@example.com", "phone": "9876543210", "department": "Computer Science",
                "year": 3, "hostel_block": "Block A", "room_no": "A-204", "parent_phone": "9876512345"}


def seed_demo_data(conn):
    """Insert the demo warden and demo students if they do not exist.
    Passwords are stored only as salted hashes."""
    if not get_warden_by_username(conn, DEMO_WARDEN["username"]):
        conn.execute(
            "INSERT INTO wardens (username,name,designation,phone,password_hash) VALUES (?,?,?,?,?)",
            (DEMO_WARDEN["username"], DEMO_WARDEN["name"], DEMO_WARDEN["designation"],
             DEMO_WARDEN["phone"], generate_password_hash(DEMO_WARDEN["password"])))
    if not get_student_by_login(conn, DEMO_STUDENT["student_id"]):
        create_student(conn, DEMO_STUDENT, DEMO_STUDENT["password"])
    second = {"student_id": "21EC014", "name": "Priya Sharma", "email": "priya@example.com",
              "phone": "9876543211", "department": "Electronics", "year": 2,
              "hostel_block": "Block B", "room_no": "B-110", "parent_phone": "9876512346"}
    if not get_student_by_login(conn, second["student_id"]):
        create_student(conn, second, "Student@123")
    conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database created at", DB_PATH)
    print("Demo warden : warden / Warden@123")
    print("Demo student: 21CS001 / Student@123")
