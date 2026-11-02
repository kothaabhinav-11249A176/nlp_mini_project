"""Builds docs/Project_Report.docx and docs/User_Manual.pdf from the diagrams and genuine screenshots."""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether
from PIL import Image as PILImage

SS, DG = "docs/screenshots/", "docs/diagrams/"
TITLE = "Smart Hostel Outpass Management System Using Natural Language Processing (NLP)"

def img_size(path, max_w):
    w, h = PILImage.open(path).size
    return max_w, max_w * h / w

# ------------------------------------------------------------------ REPORT
d = Document()
st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
for s in d.sections:
    s.left_margin = s.right_margin = Inches(1); s.top_margin = s.bottom_margin = Inches(0.9)

def H(t, l=1): d.add_heading(t, level=l)
def P(t): p = d.add_paragraph(t); p.paragraph_format.space_after = Pt(6); return p
def B(items):
    for i in items: d.add_paragraph(i, style="List Bullet")
def FIG(path, cap, w=6.2):
    d.add_picture(path, width=Inches(w)); d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = d.add_paragraph(cap); c.alignment = WD_ALIGN_PARAGRAPH.CENTER; c.runs[0].italic = True; c.runs[0].font.size = Pt(9)
def TABLE(rows, widths=None, header=True):
    t = d.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = t.cell(i, j); cell.text = str(v)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9); run.bold = (i == 0 and header)
    d.add_paragraph()

t = d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("\n\n\nMINI PROJECT REPORT"); r.bold = True; r.font.size = Pt(14)
t = d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("\n" + TITLE); r.bold = True; r.font.size = Pt(22); r.font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)
t = d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run("\n\nSubmitted by: [Student Name]   |   Register No.: [Register Number]\nDepartment: [Department]   |   Guide: [Guide Name]\n[College Name]   |   Academic Year: [Year]\n\n(Replace the bracketed placeholders before submission.)").italic = True
d.add_page_break()

H("Abstract")
P("Hostel outpass requests are traditionally written on paper or entered through long forms, which is slow for students and wardens. "
  "This project presents a web-based Smart Hostel Outpass Management System in which a student types a request in ordinary English. "
  "A Python NLP pipeline preprocesses and tokenizes the message, classifies the reason using a TF-IDF + Naive Bayes model, extracts the destination, date and return time with rule-based methods, "
  "detects missing information and suggests a priority. The structured application is stored in SQLite and reviewed by the warden, who can approve or reject it with remarks. "
  "Approved requests generate a PDF digital outpass containing a QR code that can be verified at the gate. The system is built with Flask, SQLite, Bootstrap, scikit-learn, ReportLab and the qrcode library.")

H("1. Introduction")
P("Outpass management is a routine hostel activity. Students must state why they are leaving, where they are going, on which day and when they will return, and the warden must check, decide and record the decision. "
  "Manual systems cause delays, lost slips and difficulty in tracking history. A computerised system with a natural-language interface reduces the effort for students and makes data structured for the warden.")
H("1.1 Objectives", 2)
B(["Allow students to submit outpass requests as free text.", "Extract reason, destination, date, return time and priority automatically using NLP.",
   "Detect missing information and let the student confirm the structured application.", "Provide a warden dashboard to review, approve or reject requests with remarks.",
   "Generate a digital outpass PDF with a QR code for verification.", "Store all requests and decisions persistently with proper security."])
H("1.2 Scope", 2)
P("The system covers one hostel with one or more wardens and any number of students. It is designed as a lightweight demonstration project running on a personal laptop. English text input is supported.")

H("2. System Analysis")
H("2.1 Existing system", 2)
P("Paper slips or spreadsheets: slow approval, no priority information, no easy history, easy to forge, and manual record keeping.")
H("2.2 Proposed system", 2)
P("A Flask web application with student and warden modules, NLP-based form filling, role-based access, an audit trail (approval history) and verifiable QR outpasses.")
H("2.3 Technologies used", 2)
TABLE([["Layer", "Technology"], ["Frontend", "HTML5, CSS3, JavaScript, Bootstrap 5 (bundled locally), Bootstrap Icons"], ["Backend", "Python 3, Flask"],
       ["Database", "SQLite (sqlite3 module)"], ["NLP", "Regular expressions, custom stop-word list, scikit-learn (TF-IDF, Multinomial Naive Bayes)"],
       ["QR / PDF", "qrcode, ReportLab"], ["Security", "Werkzeug password hashing, Flask sessions, CSRF tokens, HMAC signatures"]])

H("3. System Design")
H("3.1 Architecture", 2); FIG(DG + "arch.png", "Figure 1: System architecture diagram")
H("3.2 Data flow diagram", 2); FIG(DG + "dfd.png", "Figure 2: Data flow diagram")
H("3.3 Use case diagram", 2); FIG(DG + "usecase.png", "Figure 3: Use case diagram", 5.8)
H("3.4 Database design", 2)
P("The database has four tables. students and wardens store user accounts with password hashes. outpass_requests stores the original text, the structured NLP result (including the full analysis as JSON), the status (Pending, Approved, Rejected) and the deciding warden. approval_history is an audit log with one row for each submission and decision.")
FIG(DG + "er.png", "Figure 4: Entity-relationship diagram", 6.4)

H("4. NLP Module")
FIG(DG + "nlp.png", "Figure 5: NLP workflow diagram", 4.3)
TABLE([["Step", "Method", "Type"],
       ["Preprocessing (lower-case, symbol removal)", "Regex", "Rule-based"], ["Tokenization", "Regex word tokenizer (keeps 6:30 together)", "Rule-based"],
       ["Stop-word removal", "Custom list; negations such as 'not' are kept", "Rule-based"],
       ["Reason classification (6 classes)", "TF-IDF (1-2 grams) + Multinomial Naive Bayes, trained by train_model.py on 120 sentences; keyword fallback when confidence is low", "Machine learning (+ rule fallback)"],
       ["Date extraction", "today, tomorrow, day after tomorrow, weekdays, '15 November', 'Nov 9', dd/mm/yyyy, 'in N days'", "Rule-based"],
       ["Time extraction", "6 PM, 8:30 pm, 18:00, 'by evening'; context words decide return vs departure", "Rule-based"],
       ["Destination extraction", "Capitalised organisation names, place dictionary, 'to/at <noun phrase>' pattern, category default", "Rule-based"],
       ["Priority suggestion", "Urgency keywords and category", "Rule-based"], ["Missing-information detection", "Checks destination, date and return time", "Rule-based"]])
P("Classifier evaluation: 5-fold cross-validation accuracy on the 120-sentence training set is approximately 77% (standard deviation about 6%). This is measured on a small, hand-written dataset and should be seen as a rough indicator only. "
  "Because accuracy is limited, the student reviews and may edit every extracted value before submission, and the warden makes the final decision.")
P("Example: \"I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM.\" -> Reason: Medical; Destination: Hospital; Date: the actual date of tomorrow; Return time: 6:00 PM; Priority: High.")

H("5. Implementation")
B(["app.py - routes, authentication, validation, PDF and QR generation.", "nlp_processing.py - the NLP pipeline.", "database.py - schema and all SQL (parameterised).",
   "train_model.py - reproducible model training; data/training_data.csv - the dataset.", "templates/ and static/ - 15 Jinja2 pages, CSS and JavaScript.", "tests/ - 19 automated tests."])
H("5.1 Security measures", 2)
B(["Salted password hashes (scrypt) - no plain-text passwords in code or database.", "Session-based login; role checks on every protected route; students receive 403 on warden pages.",
   "CSRF token on all POST requests.", "Parameterised SQL queries only.", "Server-side validation of all inputs (name, phone, e-mail, password strength, dates, times).",
   "Students can only see their own requests (others return 404).", "QR verification links are signed with HMAC so numbers cannot be guessed."])

H("6. Testing")
P("Automated tests (tests/test_nlp.py and tests/test_app.py) were run in the development environment (Linux, Python 3.12): 19 tests, all passed. "
  "The complete workflow - registration, login, request, NLP analysis, warden approval, PDF and QR - was exercised both by tests and by a scripted browser session that produced the screenshots in this report. "
  "The application has not been run on Windows 11 by the author of this package; please run the test command on your laptop to confirm.")
TABLE([["ID", "Scenario", "Expected result", "Result"],
 ["T01", "Student registration", "Account created, hashed password", "Pass"], ["T02", "Duplicate / weak registration", "Rejected with error", "Pass"],
 ["T03", "Student login", "Dashboard opens", "Pass"], ["T04", "Invalid login / SQL-injection string", "401, error message", "Pass"],
 ["T05", "POST without CSRF token", "400", "Pass"], ["T06", "NL request: hospital sentence", "Medical / Hospital / tomorrow / 6 PM / High", "Pass"],
 ["T07", "Reason classification (5 categories)", "Correct label", "Pass"], ["T08", "Date extraction (10 patterns)", "Correct dates", "Pass"],
 ["T09", "Time extraction (6 patterns)", "Correct times", "Pass"], ["T10", "Destination extraction", "Correct place / none", "Pass"],
 ["T11", "Missing-information detection", "Gaps listed", "Pass"], ["T12", "Warden login (valid / invalid)", "Dashboard / 401", "Pass"],
 ["T13", "Approval", "Status Approved, outpass number, history rows", "Pass"], ["T14", "Rejection needs remark", "Blocked until remark given", "Pass"],
 ["T15", "Duplicate request same date", "Blocked", "Pass"], ["T16", "Unauthorised access (anonymous / student)", "Redirect / 403", "Pass"],
 ["T17", "Other student's request / PDF", "404 / 403", "Pass"], ["T18", "PDF generation", "Valid PDF, only after approval", "Pass"],
 ["T19", "QR generation and verification", "PNG; valid link OK, tampered link invalid", "Pass"]])

H("7. Results - Screenshots")
P("All screenshots below were captured from the running application with demo data.")
for f, c in [("01_home", "Home page"), ("02_student_register", "Student registration"), ("03_student_login", "Student login"), ("04_student_dashboard", "Student dashboard"),
             ("05_student_profile", "Student profile"), ("06_request_form", "Natural-language request form"), ("07_nlp_analysis", "NLP analysis result page"),
             ("08_request_status", "Request status page"), ("09_my_requests", "My requests"), ("10_warden_login", "Warden login"), ("11_warden_dashboard", "Warden dashboard"),
             ("12_warden_review", "Request review page"), ("13_after_approval", "After approval"), ("15_warden_outpass_page", "Approved digital outpass page")]:
    FIG(SS + f + ".png", "Figure: " + c, 6.0)
FIG(SS + "16_outpass_pdf-1.png", "Figure: Digital outpass PDF with QR code", 4.2)

H("8. Limitations and Future Enhancements")
B(["Small training set; larger data or a transformer model would improve classification.", "English only; multilingual input could be added.", "Rule-based date/destination extraction does not cover every phrasing.",
   "No SMS/e-mail notifications; no automatic late-return tracking.", "Flask development server and SQLite are suitable for demonstration, not heavy production use."])
H("9. Conclusion")
P("The project demonstrates how simple NLP techniques can turn free-text requests into structured, reviewable applications and how a complete approval workflow with a verifiable digital outpass can be delivered with lightweight open-source tools.")
H("10. References")
B(["Flask documentation - https://flask.palletsprojects.com", "scikit-learn documentation - https://scikit-learn.org", "ReportLab User Guide - https://www.reportlab.com/docs/",
   "python-qrcode - https://pypi.org/project/qrcode/", "Bootstrap 5 documentation - https://getbootstrap.com", "Jurafsky & Martin, Speech and Language Processing."])
d.save("docs/Project_Report.docx"); print("report ok")

# ------------------------------------------------------------------ USER MANUAL (PDF)
ss = getSampleStyleSheet()
h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=colors.HexColor("#1e3a8a"), spaceBefore=10)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#0d9488"))
body = ParagraphStyle("b", parent=ss["BodyText"], leading=15, spaceAfter=6)
cap = ParagraphStyle("c", parent=ss["BodyText"], fontSize=8, textColor=colors.grey, alignment=1)
code = ParagraphStyle("code", parent=ss["Code"], backColor=colors.HexColor("#f1f5f9"), borderPadding=4, fontSize=8.5, leading=11)
doc = SimpleDocTemplate("docs/User_Manual.pdf", pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm, title="User Manual")
S = []
def shot(f, c, w=150*mm):
    W, Hh = img_size(SS + f + ".png", w)
    if Hh > 190*mm: W, Hh = W * 190*mm / Hh, 190*mm
    S.append(KeepTogether([Image(SS + f + ".png", W, Hh), Paragraph(c, cap), Spacer(1, 6)]))
def step(t): S.append(Paragraph(t, body))
S += [Spacer(1, 50*mm), Paragraph("User Manual", ParagraphStyle("t", parent=ss["Title"], fontSize=30, textColor=colors.HexColor("#1e3a8a"))),
      Paragraph("Smart Hostel Outpass Management System Using NLP", ParagraphStyle("s", parent=ss["Title"], fontSize=16)),
      Spacer(1, 10*mm), Paragraph("For students and hostel wardens. Screenshots are from the running application.", ParagraphStyle("x", parent=body, alignment=1)), PageBreak()]
S += [Paragraph("1. Installation (Windows 11, PowerShell)", h1),
      Paragraph("Install Python 3.10 or newer from python.org and tick <b>Add python.exe to PATH</b>. Then run these commands in PowerShell:", body),
      Paragraph("Expand-Archive -Path \"$HOME\\Downloads\\outpass_system.zip\" -DestinationPath \"$HOME\\Desktop\" -Force<br/>cd \"$HOME\\Desktop\\outpass_system\"<br/>python -m venv venv<br/>.\\venv\\Scripts\\Activate.ps1<br/>python -m pip install --upgrade pip<br/>pip install -r requirements.txt<br/>python init_db.py<br/>python train_model.py<br/>python seed_demo_requests.py<br/>python app.py", code),
      Paragraph("If activation is blocked, run <font face='Courier'>Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned</font> once. "
                "Open <b>http://127.0.0.1:5000</b> in Chrome or Edge. Press Ctrl+C in PowerShell to stop the server.", body),
      Paragraph("Demo logins", h2),
      Table([["Role", "Login", "Password"], ["Warden", "warden", "Warden@123"], ["Student", "21CS001", "Student@123"], ["Student", "21EC014", "Student@123"]], colWidths=[40*mm, 50*mm, 50*mm],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .5, colors.grey)])), PageBreak()]
S += [Paragraph("2. Student guide", h1), Paragraph("2.1 Home, registration and login", h2)]
shot("01_home", "Home page", 140*mm)
step("Click <b>Register</b>, fill in your details (10-digit phone, password of 8+ characters with letters and digits) and submit. Then log in with your Student ID or e-mail.")
shot("02_student_register", "Registration page", 120*mm); shot("03_student_login", "Student login", 120*mm)
S += [Paragraph("2.2 Dashboard and profile", h2)]; shot("04_student_dashboard", "Student dashboard with request counts"); shot("05_student_profile", "Profile page", 130*mm)
S += [Paragraph("2.3 Submit a request in natural language", h2),
      Paragraph("Click <b>New Request</b> and type your message, for example: <i>I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM.</i> Include the reason, place, day and return time.", body)]
shot("06_request_form", "Request form with example buttons")
S += [Paragraph("2.4 Check the NLP analysis", h2), Paragraph("Press <b>Analyze with NLP</b>. The page shows the tokens, the detected reason, destination, date, return time and suggested priority. "
      "If information is missing the fields are highlighted - fill them in. You may correct any value, then click <b>Submit to Warden</b>.", body)]
shot("07_nlp_analysis", "NLP analysis and confirmation page")
S += [Paragraph("2.5 Track status and download the outpass", h2), Paragraph("The status page shows a timeline. When the warden approves, <b>View Digital Outpass</b> and <b>Download PDF</b> appear. Show the PDF (with its QR code) at the gate.", body)]
shot("08_request_status", "Request status page"); shot("09_my_requests", "My requests list")
shot("14_student_outpass_page", "Digital outpass page"); shot("16_outpass_pdf-1", "Downloaded PDF outpass", 110*mm)
S += [PageBreak(), Paragraph("3. Warden guide", h1), Paragraph("3.1 Login and dashboard", h2),
      Paragraph("Use <b>Warden Login</b> (warden / Warden@123). The dashboard lists all requests, pending first and sorted by priority. Use the search box and filters to find requests.", body)]
shot("10_warden_login", "Warden login", 120*mm); shot("11_warden_dashboard", "Warden dashboard")
S += [Paragraph("3.2 Review, approve or reject", h2), Paragraph("Click <b>Review</b> to see the student's details, the original message, the NLP-extracted information, the suggested priority and the history. "
      "Enter remarks and click <b>Approve</b> or <b>Reject</b> (a remark is mandatory for rejection). A decision cannot be changed afterwards.", body)]
shot("13_after_approval", "Request after approval"); shot("15_warden_outpass_page", "Digital outpass opened by the warden")
S += [Paragraph("4. Troubleshooting", h1),
      Table([["Problem", "Solution"], ["'python' is not recognised", "Reinstall Python and tick 'Add to PATH', then reopen PowerShell."],
             ["Script activation blocked", "Run Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned"],
             ["Port 5000 already in use", "Close the other program or change the port in the last line of app.py."],
             ["Start with clean data", "python init_db.py --reset, then python seed_demo_requests.py"],
             ["Session expired / 400 error", "Reload the page and try again (CSRF token refresh)."]], colWidths=[55*mm, 110*mm],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")), ("GRID", (0, 0), (-1, -1), .5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))]
doc.build(S); print("manual ok")
