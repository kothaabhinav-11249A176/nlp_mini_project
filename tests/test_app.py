"""Integration tests for the Flask app (uses a temporary database).
Run:  python -m unittest discover -s tests -v"""
import os, re, sys, tempfile, unittest
from datetime import date, timedelta

_tmp = tempfile.mkdtemp()
os.environ["OUTPASS_DB"] = os.path.join(_tmp, "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod          # noqa: E402
import database as db         # noqa: E402

MSG = "I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM."


def token(client, url="/login"):
    html = client.get(url).get_data(as_text=True)
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


def login_student(client, ident="21CS001", pw="Student@123"):
    return client.post("/login", data={"_csrf": token(client), "identifier": ident, "password": pw})


def login_warden(client, user="warden", pw="Warden@123"):
    return client.post("/warden/login", data={"_csrf": token(client, "/warden/login"), "username": user, "password": pw})


def submit(client, msg=MSG):
    """Run the full student flow; returns the response of the confirm step."""
    t = token(client, "/student/request")
    client.post("/student/request", data={"_csrf": t, "message": msg})
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return client.post("/student/request/confirm", data={
        "_csrf": t, "category": "Medical", "destination": "Hospital",
        "departure_date": tomorrow, "return_time": "18:00", "departure_time": ""})


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def setUp(self):
        appmod.app.config["TESTING"] = True
        self.c = appmod.app.test_client()

    def test_01_registration(self):
        t = token(self.c, "/register")
        data = {"_csrf": t, "name": "Test Student", "student_id": "22IT099", "email": "t@example.com",
                "phone": "9000000001", "department": "Information Technology", "year": "2",
                "hostel_block": "Block C", "room_no": "C-1", "parent_phone": "", "password": "Passw0rdX",
                "confirm_password": "Passw0rdX"}
        r = self.c.post("/register", data=data)
        self.assertEqual(r.status_code, 302)
        # duplicate ID rejected
        r = self.c.post("/register", data=data)
        self.assertEqual(r.status_code, 400)
        # weak password / bad phone rejected
        bad = dict(data, student_id="22IT100", email="z@example.com", password="abc", confirm_password="abc", phone="12")
        self.assertEqual(self.c.post("/register", data=bad).status_code, 400)
        # password is hashed in the DB
        conn = db.get_conn()
        h = db.get_student_by_login(conn, "22IT099")["password_hash"]
        conn.close()
        self.assertNotIn("Passw0rdX", h)
        self.assertTrue(h.startswith(("scrypt:", "pbkdf2:")))

    def test_02_student_login_and_invalid(self):
        self.assertEqual(login_student(self.c).status_code, 302)
        self.assertEqual(self.c.get("/student/dashboard").status_code, 200)
        c2 = appmod.app.test_client()
        self.assertEqual(login_student(c2, pw="wrong").status_code, 401)
        self.assertEqual(login_student(c2, ident="nobody").status_code, 401)

    def test_03_csrf_required(self):
        r = self.c.post("/login", data={"identifier": "21CS001", "password": "Student@123"})
        self.assertEqual(r.status_code, 400)

    def test_04_request_flow_and_analysis_page(self):
        login_student(self.c)
        t = token(self.c, "/student/request")
        r = self.c.post("/student/request", data={"_csrf": t, "message": MSG})
        self.assertEqual(r.status_code, 302)
        page = self.c.get("/student/analysis").get_data(as_text=True)
        self.assertIn("Medical", page)
        self.assertIn("Hospital", page)
        # too-short message rejected
        self.assertEqual(self.c.post("/student/request", data={"_csrf": t, "message": "hi"}).status_code, 400)

    def test_05_full_workflow_approve_pdf_qr(self):
        s = appmod.app.test_client()
        login_student(s, "21EC014")
        r = submit(s)
        self.assertEqual(r.status_code, 302)
        rid = int(r.headers["Location"].rstrip("/").split("/")[-1])
        # duplicate for same date blocked
        self.assertEqual(submit(s).status_code, 400)
        # PDF not available before approval
        self.assertEqual(s.get("/outpass/%d/pdf" % rid).status_code, 403)
        # warden approves
        w = appmod.app.test_client()
        self.assertEqual(login_warden(w).status_code, 302)
        self.assertIn("Priya Sharma", w.get("/warden/dashboard").get_data(as_text=True))
        self.assertEqual(w.get("/warden/request/%d" % rid).status_code, 200)
        t = token(w, "/warden/request/%d" % rid)
        r = w.post("/warden/request/%d/decide" % rid, data={"_csrf": t, "decision": "Approved", "remarks": "OK"})
        self.assertEqual(r.status_code, 302)
        # cannot decide twice
        w.post("/warden/request/%d/decide" % rid, data={"_csrf": t, "decision": "Rejected", "remarks": "late"})
        conn = db.get_conn()
        row = db.get_request(conn, rid)
        self.assertEqual(row["status"], "Approved")
        self.assertTrue(row["outpass_no"].startswith("OP"))
        self.assertEqual(len(db.get_history(conn, rid)), 2)
        conn.close()
        # student downloads PDF
        pdf = s.get("/outpass/%d/pdf" % rid)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        self.assertGreater(len(pdf.data), 3000)
        # QR code is a PNG
        qr = s.get("/outpass/%d/qr.png" % rid)
        self.assertEqual(qr.status_code, 200)
        self.assertTrue(qr.data.startswith(b"\x89PNG"))
        # QR verification link works, tampered link fails
        url = appmod.sign(row["outpass_no"])
        self.assertEqual(self.c.get("/verify/%s/%s" % (row["outpass_no"], url)).status_code, 200)
        self.assertEqual(self.c.get("/verify/%s/%s" % (row["outpass_no"], "0" * 16)).status_code, 404)
        # another student cannot access this outpass
        other = appmod.app.test_client()
        login_student(other)
        self.assertIn(other.get("/outpass/%d/pdf" % rid).status_code, (403, 404))
        self.assertEqual(other.get("/student/request/%d" % rid).status_code, 404)

    def test_06_rejection_needs_remark(self):
        s = appmod.app.test_client()
        login_student(s)
        tomorrow = (date.today() + timedelta(days=5)).isoformat()
        t = token(s, "/student/request")
        s.post("/student/request", data={"_csrf": t, "message": "Going to the mall for shopping on a weekend"})
        r = s.post("/student/request/confirm", data={"_csrf": t, "category": "Shopping", "destination": "Mall",
                                                   "departure_date": tomorrow, "return_time": "20:00"})
        rid = int(r.headers["Location"].rstrip("/").split("/")[-1])
        w = appmod.app.test_client()
        login_warden(w)
        t = token(w, "/warden/request/%d" % rid)
        w.post("/warden/request/%d/decide" % rid, data={"_csrf": t, "decision": "Rejected", "remarks": ""})
        conn = db.get_conn(); self.assertEqual(db.get_request(conn, rid)["status"], "Pending"); conn.close()
        w.post("/warden/request/%d/decide" % rid, data={"_csrf": t, "decision": "Rejected", "remarks": "Exam week"})
        conn = db.get_conn(); row = db.get_request(conn, rid); conn.close()
        self.assertEqual(row["status"], "Rejected")
        self.assertIsNone(row["outpass_no"])
        self.assertEqual(w.get("/warden/outpass/%d" % rid).status_code, 302)  # no outpass for rejected

    def test_07_invalid_inputs_rejected(self):
        s = appmod.app.test_client(); login_student(s)
        t = token(s, "/student/request")
        s.post("/student/request", data={"_csrf": t, "message": "I want to go to the bank tomorrow"})
        past = (date.today() - timedelta(days=1)).isoformat()
        r = s.post("/student/request/confirm", data={"_csrf": t, "category": "Other", "destination": "Bank",
                                                   "departure_date": past, "return_time": "18:00"})
        self.assertEqual(r.status_code, 400)
        r = s.post("/student/request/confirm", data={"_csrf": t, "category": "Other", "destination": "",
                                                   "departure_date": "garbage", "return_time": "99:99"})
        self.assertEqual(r.status_code, 400)

    def test_08_unauthorized_access(self):
        anon = appmod.app.test_client()
        for url in ("/warden/dashboard", "/warden/request/1", "/warden/outpass/1"):
            self.assertEqual(anon.get(url).status_code, 302, url)
        for url in ("/student/dashboard", "/student/request", "/student/requests", "/student/profile"):
            self.assertEqual(anon.get(url).status_code, 302, url)
        self.assertEqual(anon.get("/outpass/1/pdf").status_code, 403)
        # a logged-in STUDENT cannot open warden pages or approve
        s = appmod.app.test_client(); login_student(s)
        self.assertEqual(s.get("/warden/dashboard").status_code, 403)
        t = token(s, "/student/request")
        self.assertEqual(s.post("/warden/request/1/decide", data={"_csrf": t, "decision": "Approved"}).status_code, 403)
        # student credentials do not work on the warden login
        self.assertEqual(login_warden(appmod.app.test_client(), "21CS001", "Student@123").status_code, 401)

    def test_09_warden_invalid_login(self):
        self.assertEqual(login_warden(appmod.app.test_client(), pw="bad").status_code, 401)

    def test_10_sql_injection_attempt(self):
        c = appmod.app.test_client()
        r = login_student(c, ident="' OR '1'='1", pw="x")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
