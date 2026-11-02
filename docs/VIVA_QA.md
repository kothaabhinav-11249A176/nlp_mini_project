# Viva Questions and Answers

**1. What is the aim of the project?** To let hostel students request outpasses in natural language; NLP converts the text into a structured application which the warden approves or rejects, producing a digital outpass with a QR code.

**2. Which technologies are used?** Python Flask (backend), SQLite (database), HTML/CSS/JavaScript with Bootstrap (frontend), scikit-learn (ML), regular expressions (rule-based NLP), qrcode and ReportLab (QR and PDF).

**3. Which parts are machine learning and which are rule-based?** Only reason classification uses ML (TF-IDF + Multinomial Naive Bayes). Tokenization, stop-word removal, date/time/destination extraction, priority and missing-information detection are rule-based.

**4. Why did you not use only ML?** Dates, times and places follow patterns that rules extract reliably without large datasets; ML is useful where wording varies (classifying the reason).

**5. What is tokenization?** Splitting text into words/tokens, e.g. "return by 6 PM" -> `return`, `by`, `6`, `pm`.

**6. What are stop words and why remove them?** Very common words (the, to, is) that carry little meaning for classification; removing them reduces noise. Negations like "not" are deliberately kept.

**7. What is TF-IDF?** Term Frequency-Inverse Document Frequency gives high weight to words frequent in a sentence but rare across all sentences (e.g. "hospital"), turning text into numeric vectors.

**8. Why Naive Bayes?** It works well on small text datasets, trains in milliseconds, is simple to explain and gives class probabilities used as the confidence value.

**9. How accurate is the model?** About 77 % in 5-fold cross-validation on 120 sentences (see `data/training_report.txt`). It is a small dataset, so students can correct the category before submitting.

**10. How is "tomorrow" converted to a real date?** The regex finds "tomorrow" and Python adds one day to `date.today()`.

**11. How does missing-information detection work?** After extraction, empty fields (destination, date, return time) are listed; the analysis page highlights them and the student must fill them before submitting.

**12. How is priority suggested?** Rules: urgency words or Medical -> High; Family Function/Academic -> Medium; others -> Low. It is only a suggestion; the warden decides.

**13. How are passwords protected?** Hashed with Werkzeug's salted `scrypt` hash; plain passwords are never stored.

**14. How is role-based access control done?** The session stores a role. Decorators `student_required` and `warden_required` guard routes; a student opening a warden page gets 403.

**15. What is CSRF and how do you prevent it?** An attack that makes a logged-in user's browser send unwanted requests. Every POST form carries a random token that is compared with the session token.

**16. How do you prevent SQL injection?** All queries use `?` placeholders with parameters rather than string concatenation.

**17. What does the QR code contain?** A verification URL with the outpass number and an HMAC signature, so a forged number cannot be validated.

**18. What database tables exist?** students, wardens, outpass_requests, approval_history, linked by foreign keys (1 student : N requests, 1 request : N history rows).

**19. What happens if two requests are made for the same date?** The system blocks the second Pending/Approved request for that date.

**20. What are the limitations?** Small training data, English only, limited date phrases, Flask dev server, no e-mail/SMS notifications.

**21. Future enhancements?** Larger dataset or transformer model, spaCy NER, Hindi/Tamil support, SMS alerts to parents, face/ID check at the gate, mobile app.

**22. How would you deploy it for real?** Production WSGI server (Waitress on Windows), HTTPS, a secret key from the environment, a stronger database, and changed demo passwords.
