# Smart Hostel Outpass Management System using NLP

A Flask + SQLite web application where students request hostel outpasses **in plain English**.
An NLP pipeline extracts the reason, destination, date, return time and a suggested priority;
the warden reviews, approves or rejects, and approved requests produce a **PDF outpass with a QR code**.

## What is rule-based and what is machine learning (honest summary)

| Feature | Technique |
|---|---|
| Preprocessing, tokenization, stop-word removal | Rule-based (regex + stop-word list) |
| **Reason classification** (Medical, Family Function, Personal Work, Academic, Shopping, Other) | **ML**: TF-IDF + Multinomial Naive Bayes trained on `data/training_data.csv` (120 hand-written sentences). A keyword classifier is used as fallback / when the ML model is very unsure |
| Date, time, destination extraction | Rule-based (regex + place dictionary) |
| Entities, priority suggestion, missing-information detection | Rule-based |

The model is **really trained** by `train_model.py`. Its 5-fold cross-validation accuracy on the small dataset
is about **77 %** (see `data/training_report.txt`), so the student always reviews/edits the extracted
values before submitting. No spaCy/NLTK is needed, which keeps installation easy on Windows.

## Demo accounts

| Role | Login | Password |
|---|---|---|
| Warden | `warden` | `Warden@123` |
| Student | `21CS001` (Arun Kumar) | `Student@123` |
| Student | `21EC014` (Priya Sharma) | `Student@123` |

Passwords are stored only as salted hashes (Werkzeug `scrypt`). Change the demo warden password before any real use.

## Windows 11 installation (PowerShell)

Prerequisite: Python 3.10+ from https://www.python.org/downloads/ (tick **"Add python.exe to PATH"** in the installer).

```powershell
# 1. Extract the ZIP (right-click > Extract All...) or:
Expand-Archive -Path "$HOME\Downloads\outpass_system.zip" -DestinationPath "$HOME\Desktop" -Force

# 2. Open the project folder
cd "$HOME\Desktop\outpass_system"

# 3. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1
```
If PowerShell says *"running scripts is disabled"*, run this once and activate again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
```powershell
# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Create the database (tables + demo accounts) and train the NLP model
python init_db.py
python train_model.py

# 6. (Optional) add sample requests so the dashboards are not empty
python seed_demo_requests.py

# 7. (Optional) run the automated tests
python -m unittest discover -s tests -v

# 8. Start the application
python app.py
```
Open **http://127.0.0.1:5000** in Chrome/Edge. Stop the server with `Ctrl + C`.

## Demo walkthrough

1. **Student**: Login (`21CS001` / `Student@123`) -> *New Request* -> type
   `I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM.`
   -> *Analyze with NLP* -> check the extracted fields -> *Submit to Warden*.
2. Click *Logout*. Open *Warden Login* (`warden` / `Warden@123`).
3. **Warden**: Dashboard -> *Review* the pending request -> add a remark -> *Approve* (or *Reject*, remark required).
4. Log in as the student again -> *My Requests* -> *View Digital Outpass* -> *Download PDF* (contains a QR code).
5. Scan the QR code (or open the printed link) to see the public verification page.
   Note: the QR contains the address of the computer running the app (`127.0.0.1` on your laptop). To scan it from a phone,
   start the app on your Wi-Fi IP: `python app.py` then browse using `http://<laptop-ip>:5000` — or simply demonstrate the link in the laptop browser.

## Project structure

```
outpass_system/
  app.py                  Flask routes, auth, validation, PDF + QR
  nlp_processing.py       NLP pipeline
  database.py             SQLite schema + queries
  init_db.py              creates database + demo accounts
  train_model.py          trains the reason classifier
  seed_demo_requests.py   optional sample data
  tools_screenshots.py    script that produced docs/screenshots (needs playwright)
  requirements.txt
  data/training_data.csv  120 labelled training sentences
  templates/  static/css  static/js  static/vendor (Bootstrap, bundled offline)
  tests/                  test_nlp.py, test_app.py
  docs/                   report, user manual, diagrams, screenshots, test cases, viva Q&A
```

## Security features

Password hashing - session cookies (HttpOnly, SameSite) - role-based access control - CSRF token on every POST - parameterised SQL
(no string-built queries) - input validation - duplicate-request blocking - HMAC-signed QR verification links - 403/404 handling
so a student cannot open other students' requests or any warden page.

## Known limitations

* Classifier is trained on a small dataset; unusual wording may be mis-classified (student can correct it before submitting).
* English only. Date parsing covers common patterns, not every possible phrase.
* Built for demonstration (Flask development server, SQLite). For real deployment use a production WSGI server, HTTPS and a real secret key (`OUTPASS_SECRET`).
