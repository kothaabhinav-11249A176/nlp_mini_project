"""seed_demo_requests.py - OPTIONAL: adds a few realistic sample requests so the
warden dashboard is not empty during a demo.  Run after init_db.py."""
from datetime import date, timedelta
import database as db
import nlp_processing as nlp

SAMPLES = [
    ("21CS001", "Need to visit Apollo Hospital urgently today for a fever checkup, will return by 9 pm", 0, None, None),
    ("21EC014", "Going home on Saturday to attend my cousin's wedding, will be back by 8 PM on Sunday.", 3, None, None),
    ("21CS001", "I want to go to the mall for shopping on Friday evening and return by 8:30 PM.", 5, "Approved", "Approved. Be back on time."),
    ("21EC014", "I have a placement interview at Infosys office day after tomorrow, back by 5 pm.", 2, "Rejected", "Lab exam on that day. Reschedule."),
]
conn = db.get_conn()
wardens = conn.execute("SELECT id FROM wardens LIMIT 1").fetchone()
for sid, text, offset, decision, remark in SAMPLES:
    s = db.get_student_by_login(conn, sid)
    info = nlp.analyze_request(text)
    info["departure_date"] = (date.today() + timedelta(days=offset)).isoformat()
    info["destination"] = (info["destination"] or "Not specified").replace(" (inferred)", "")
    info["return_time"] = info["return_time"] or "18:00"
    if db.find_duplicate(conn, s["id"], info["departure_date"], info["return_time"]):
        continue
    rid = db.create_request(conn, s["id"], info)
    if decision:
        db.decide_request(conn, rid, wardens["id"], decision, remark)
print("Sample requests added.")
