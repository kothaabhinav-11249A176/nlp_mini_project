"""
nlp_processing.py - NLP pipeline for the Smart Hostel Outpass system.

WHAT IS RULE-BASED AND WHAT IS ML (honest summary)
--------------------------------------------------
ML-based (scikit-learn, TF-IDF + Multinomial Naive Bayes):
    * Reason classification (Medical / Family Function / Personal Work /
      Academic / Shopping / Other).  The model is trained from
      data/training_data.csv by train_model.py and saved to
      data/reason_model.joblib.  If that file is missing, the module trains
      the model in memory from the CSV on first use.  If scikit-learn is not
      installed, it falls back to a keyword-rule classifier.

Rule-based (regular expressions + dictionaries, no training):
    * Preprocessing, tokenization, stop-word removal
    * Date extraction (today, tomorrow, day after tomorrow, weekdays,
      "next Monday", "on 15 November", "15/11/2026", "15th Nov")
    * Time extraction ("6 PM", "6:30 pm", "18:00", "by evening", "tonight")
    * Destination extraction (known place dictionary + "to/at/visit <phrase>")
    * Missing-information detection
    * Priority suggestion
    * Structured application generation

No spaCy/NLTK is required, so installation on Windows is lightweight.
"""
import csv
import os
import re
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(BASE_DIR, "data", "training_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "data", "reason_model.joblib")

CATEGORIES = ["Medical", "Family Function", "Personal Work",
              "Academic", "Shopping", "Other"]

# --------------------------------------------------------------------------
# 1-3. Preprocessing, tokenization, stop-word removal (rule-based)
# --------------------------------------------------------------------------
STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "she", "it",
    "they", "them", "the", "a", "an", "and", "or", "but", "if", "of", "at",
    "by", "for", "with", "about", "to", "from", "in", "on", "is", "are", "was",
    "were", "be", "been", "am", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "need", "want", "please",
    "permission", "request", "sir", "madam", "kindly", "this", "that", "so",
    "as", "also", "have", "has", "had", "going", "go", "like", "get",
}
# words that look like stop words but carry meaning for us
KEEP_WORDS = {"not", "no", "after", "before", "until", "till", "back", "return"}


def preprocess(text):
    """Lower-case, strip odd characters, collapse whitespace."""
    text = (text or "").strip().lower()
    text = text.replace("\u2019", "'")
    text = re.sub(r"[^a-z0-9:/\-\s.,']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text):
    """Simple regex word tokenizer (keeps times like 6:30 together)."""
    return re.findall(r"\d{1,2}:\d{2}|\d+(?:st|nd|rd|th)?|[a-z]+(?:'[a-z]+)?", text)


def remove_stop_words(tokens):
    return [t for t in tokens if t not in STOP_WORDS or t in KEEP_WORDS]


# --------------------------------------------------------------------------
# 4. Reason classification (ML with rule-based fallback)
# --------------------------------------------------------------------------
_KEYWORDS = {
    "Medical": ["hospital", "doctor", "clinic", "fever", "unwell", "sick", "ill",
                "medicine", "medical", "pharmacy", "injury", "treatment", "dentist",
                "checkup", "check-up", "health", "pain", "scan", "blood"],
    "Family Function": ["wedding", "marriage", "family", "function", "engagement",
                        "funeral", "birthday", "festival", "ceremony", "relative",
                        "cousin", "sister", "brother", "parents", "uncle", "aunt",
                        "grandmother", "grandfather", "home", "reception"],
    "Academic": ["exam", "interview", "internship", "seminar", "workshop", "library",
                 "project", "conference", "college", "class", "lab", "placement",
                 "certification", "course", "competition", "hackathon", "symposium"],
    "Shopping": ["shopping", "buy", "purchase", "mall", "market", "groceries",
                 "clothes", "shoes", "supermarket", "stationery", "laptop", "store"],
    "Personal Work": ["bank", "passport", "aadhaar", "aadhar", "license", "office",
                      "document", "certificate", "visa", "salon", "haircut", "post",
                      "courier", "atm", "government", "registration", "renew"],
}

_model = None
_model_status = "not loaded"


def _load_training_rows():
    rows = []
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append((r["text"], r["label"]))
    return rows


def train_model(save=True):
    """Train TF-IDF + Multinomial Naive Bayes on data/training_data.csv.
    Returns (model, report_dict). Raises ImportError if sklearn missing."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score
    import joblib

    rows = _load_training_rows()
    if len(rows) < 20:
        raise RuntimeError("Training data missing or too small: " + DATA_CSV)
    X = [preprocess(t) for t, _ in rows]
    y = [l for _, l in rows]
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words=list(STOP_WORDS - KEEP_WORDS))),
        ("nb", MultinomialNB(alpha=0.3)),
    ])
    scores = cross_val_score(pipe, X, y, cv=5)
    pipe.fit(X, y)
    if save:
        joblib.dump(pipe, MODEL_PATH)
    return pipe, {"samples": len(rows), "cv_accuracy_mean": float(scores.mean()),
                  "cv_accuracy_std": float(scores.std())}


def _get_model():
    global _model, _model_status
    if _model is not None:
        return _model
    try:
        import joblib
        if os.path.exists(MODEL_PATH):
            _model = joblib.load(MODEL_PATH)
            _model_status = "loaded saved model"
        else:
            _model, _ = train_model(save=True)
            _model_status = "trained from CSV on first use"
    except Exception as exc:  # sklearn missing, CSV missing, etc.
        _model = False
        _model_status = "ML unavailable (%s) - using keyword rules" % exc
    return _model


def _keyword_classify(clean):
    tokens = set(tokenize(clean))
    best, best_score = "Other", 0
    for cat, words in _KEYWORDS.items():
        score = sum(1 for w in words if re.search(r"\b%s\b" % re.escape(w), clean))
        if score > best_score:
            best, best_score = cat, score
    conf = min(0.95, 0.5 + 0.15 * best_score) if best_score else 0.3
    return best, conf


def classify_reason(text):
    """Return (label, confidence, method)."""
    clean = preprocess(text)
    model = _get_model()
    kw_label, kw_conf = _keyword_classify(clean)
    if model:
        proba = model.predict_proba([clean])[0]
        idx = int(proba.argmax())
        label, conf = str(model.classes_[idx]), float(proba[idx])
        # If the ML model is unsure but strong keywords agree on another label,
        # trust the keywords (hybrid decision).  This is documented behaviour.
        if conf < 0.30 and kw_conf < 0.5:
            return "Other", conf, "ML low confidence, no keyword evidence -> Other"
        if conf < 0.45 and kw_conf >= 0.65:
            return kw_label, kw_conf, "Hybrid (keyword override of low-confidence ML)"
        return label, conf, "ML (TF-IDF + Naive Bayes)"
    return kw_label, kw_conf, "Rule-based keywords"


# --------------------------------------------------------------------------
# 6. Date extraction (rule-based)
# --------------------------------------------------------------------------
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9


def _safe_date(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def extract_date(text, today=None):
    """Return (date | None, matched_phrase | None)."""
    today = today or date.today()
    t = preprocess(text)

    if re.search(r"\bday after tomorrow\b", t):
        return today + timedelta(days=2), "day after tomorrow"
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", t):
        return today + timedelta(days=1), "tomorrow"
    if re.search(r"\b(today|tonight|this evening|this afternoon|this morning)\b", t):
        return today, re.search(r"\b(today|tonight|this evening|this afternoon|this morning)\b", t).group(0)
    m = re.search(r"\bin (\d{1,2}) days?\b", t)
    if m:
        return today + timedelta(days=int(m.group(1))), m.group(0)

    # dd/mm/yyyy or dd-mm-yyyy
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4}|\d{2})\b", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        dt = _safe_date(y, mo, d)
        if dt:
            return dt, m.group(0)

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    # 15 november / 15th nov / 15 nov 2026
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(%s)\b(?:\s+(\d{4}))?" % month_names, t)
    if not m:
        m2 = re.search(r"\b(%s)\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?" % month_names, t)
        if m2:
            mon, d, y = MONTHS[m2.group(1)], int(m2.group(2)), m2.group(3)
            dt = _safe_date(int(y) if y else today.year, mon, d)
            if dt and not y and dt < today:
                dt = _safe_date(today.year + 1, mon, d)
            if dt:
                return dt, m2.group(0)
    else:
        d, mon, y = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
        dt = _safe_date(int(y) if y else today.year, mon, d)
        if dt and not y and dt < today:
            dt = _safe_date(today.year + 1, mon, d)
        if dt:
            return dt, m.group(0)

    # weekdays: "on friday", "next monday"
    m = re.search(r"\b(next\s+|this\s+|coming\s+)?(%s)\b" % "|".join(WEEKDAYS), t)
    if m:
        target = WEEKDAYS.index(m.group(2))
        delta = (target - today.weekday()) % 7
        if delta == 0:          # same weekday name -> next week's occurrence
            delta = 7
        return today + timedelta(days=delta), m.group(0)

    # bare day-of-month: "on the 20th"
    m = re.search(r"\bon (?:the )?(\d{1,2})(?:st|nd|rd|th)\b", t)
    if m:
        d = int(m.group(1))
        dt = _safe_date(today.year, today.month, d)
        if dt and dt < today:
            nm = today.month % 12 + 1
            dt = _safe_date(today.year + (1 if nm == 1 else 0), nm, d)
        if dt:
            return dt, m.group(0)
    return None, None


# --------------------------------------------------------------------------
# 7. Time extraction (rule-based)
# --------------------------------------------------------------------------
_PERIOD_DEFAULTS = {"morning": "09:00", "afternoon": "15:00", "evening": "18:00",
                    "night": "21:00", "noon": "12:00", "midnight": "23:59"}


def _fmt_time(h, mi):
    return "%02d:%02d" % (h, mi)


def _parse_clock(h, mi, ap):
    h, mi = int(h), int(mi or 0)
    if ap:
        ap = ap.replace(".", "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
    if h > 23 or mi > 59:
        return None
    return _fmt_time(h, mi)


def extract_times(text):
    """Return dict(departure=..., return=...) with 'HH:MM' strings or None.
    Times after return-words (return/back/by/before/until) are the return time;
    times after leave-words (leave/start/depart/from) are departure time."""
    t = preprocess(text)
    result = {"departure": None, "return": None}
    pat = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)|\b(\d{1,2}):(\d{2})\b|\b(\d{1,2})\s*o'?clock\b")
    found = []
    for m in pat.finditer(t):
        if m.group(1):
            val = _parse_clock(m.group(1), m.group(2), m.group(3))
        elif m.group(4):
            val = _parse_clock(m.group(4), m.group(5), None)
        else:
            h = int(m.group(6))
            val = _parse_clock(h + 12 if 1 <= h <= 7 else h, 0, None)  # "6 o'clock" -> evening guess
        if val:
            found.append((m.start(), val))
    for pos, val in found:
        ctx = t[max(0, pos - 35):pos]
        if re.search(r"(return|back|reach|come|by|before|until|till|within|at hostel)[^.]*$", ctx):
            result["return"] = result["return"] or val
        elif re.search(r"(leave|leaving|start|depart|from|go at|going at)[^.]*$", ctx):
            result["departure"] = result["departure"] or val
        elif result["return"] is None and result["departure"] is not None:
            result["return"] = val
        else:
            # un-labelled single time: treat as return time (hostel cares about it)
            result["return"] = result["return"] or val
    if not found:
        m = re.search(r"(?:return|back|by|before|until|till)[^.]{0,20}\b(morning|afternoon|evening|night|noon|midnight)\b", t)
        if m:
            result["return"] = _PERIOD_DEFAULTS[m.group(1)]
        elif re.search(r"\btonight\b", t):
            result["return"] = "21:00"
    return result


def format_time_12h(hhmm):
    if not hhmm:
        return ""
    h, m = map(int, hhmm.split(":"))
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return "%d:%02d %s" % (h12, m, ap)


# --------------------------------------------------------------------------
# 5/8. Destination + named entities (rule-based)
# --------------------------------------------------------------------------
KNOWN_PLACES = {
    "hospital": "Hospital", "clinic": "Clinic", "dentist": "Dental Clinic",
    "pharmacy": "Pharmacy", "medical shop": "Pharmacy",
    "bank": "Bank", "atm": "ATM", "passport office": "Passport Office",
    "post office": "Post Office", "railway station": "Railway Station",
    "bus stand": "Bus Stand", "bus station": "Bus Stand", "airport": "Airport",
    "mall": "Shopping Mall", "market": "Market", "supermarket": "Supermarket",
    "temple": "Temple", "church": "Church", "mosque": "Mosque",
    "library": "Library", "bookstore": "Bookstore", "salon": "Salon",
    "home": "Home", "native": "Home Town", "hometown": "Home Town",
    "relative's house": "Relative's House", "uncle's house": "Relative's House",
    "aunt's house": "Relative's House", "wedding hall": "Wedding Hall",
    "marriage hall": "Wedding Hall", "town": "Town", "city": "City",
    "college": "Other College",    "cinema": "Cinema", "theatre": "Cinema", "restaurant": "Restaurant",
}
# fallback destination implied by category when no place is named
_CATEGORY_DEFAULT_DEST = {"Medical": "Hospital", "Shopping": "Market"}

_PLACE_PHRASE = re.compile(
    r"\b(?:to|at|visit|visiting|in|near|towards)\s+(?:the\s+|a\s+|my\s+)?"
    r"([a-z][a-z' ]{2,40}?)(?=\s+(?:tomorrow|today|because|since|as|for|and|to|on|by|at|before|after|"
    r"i\b|from|with|so|which|where|but|day|next|this|will|till|until|after)\b|[.,;]|$)")
_ORG_PHRASE = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+"
                         r"(?:Hospital|Clinic|Bank|College|Mall|Temple|Church|Hall|Office|Station|Market))\b")


# words that follow "to/at/in" but are not real destinations
_NOT_PLACES = {"out", "outside", "there", "here", "somewhere", "bit", "time", "now",
               "early", "late", "back", "leave", "see", "know", "be", "attend", "meet"}


def extract_destination(text, category=None):
    """Return (destination | None, method)."""
    # 1) proper-noun organisation names, e.g. "Apollo Hospital"
    m = _ORG_PHRASE.search(text or "")
    if m:
        return m.group(1), "named entity pattern"
    t = preprocess(text)
    # 2) dictionary of known places (longest key first)
    for key in sorted(KNOWN_PLACES, key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(key), t):
            return KNOWN_PLACES[key], "place dictionary"
    # 3) generic "to/at <noun phrase>"
    for m in _PLACE_PHRASE.finditer(t):
        cand = m.group(1).strip()
        words = [w for w in cand.split() if w not in STOP_WORDS and w not in _NOT_PLACES]
        if words and not re.fullmatch(r"\d+.*", words[0]) and words[0] not in (
                "visit", "attend", "buy", "get", "meet", "take", "do", "see", "be", "have"):
            return " ".join(w.capitalize() for w in words[:4]), "preposition pattern"
    # 4) default by category
    if category in _CATEGORY_DEFAULT_DEST:
        return _CATEGORY_DEFAULT_DEST[category] + " (inferred)", "category default"
    return None, "not found"


def extract_entities(text):
    """Lightweight NER: names of people/orgs written in Title Case, plus
    duration expressions."""
    ents = []
    for m in _ORG_PHRASE.finditer(text or ""):
        ents.append({"text": m.group(1), "type": "ORG/PLACE"})
    for m in re.finditer(r"\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+", text or ""):
        ents.append({"text": m.group(0), "type": "PERSON"})
    for m in re.finditer(r"\b(\d+)\s*(day|days|hour|hours|night|nights)\b", (text or "").lower()):
        ents.append({"text": m.group(0), "type": "DURATION"})
    return ents


# --------------------------------------------------------------------------
# Priority suggestion (rule-based)
# --------------------------------------------------------------------------
_URGENT_WORDS = ["emergency", "urgent", "urgently", "immediately", "accident", "critical",
                 "severe", "serious", "ambulance", "asap", "hospitalised", "hospitalized"]


def suggest_priority(text, category, req_date=None, today=None):
    t = preprocess(text)
    today = today or date.today()
    if any(w in t for w in _URGENT_WORDS):
        return "High", "Urgent/emergency keyword found"
    if category == "Medical":
        return "High", "Medical requests are prioritised"
    if re.search(r"funeral|death|passed away|expired", t):
        return "High", "Bereavement/emergency"
    if category in ("Family Function", "Academic"):
        if req_date and (req_date - today).days <= 2:
            return "Medium", "%s request for a near date" % category
        return "Medium", "%s requests are medium priority" % category
    return "Low", "Routine request"


# --------------------------------------------------------------------------
# 9. Missing-information detection + structured application
# --------------------------------------------------------------------------
def detect_missing(info):
    missing = []
    if not info.get("destination"):
        missing.append("Destination")
    if not info.get("departure_date"):
        missing.append("Date of leaving")
    if not info.get("return_time"):
        missing.append("Expected return time")
    if info.get("category") == "Other" and info.get("confidence", 1) < 0.4:
        missing.append("Clear reason for leaving")
    return missing


def analyze_request(text, today=None):
    """Full pipeline. Returns a dict that is stored in the database and shown
    on the NLP analysis page."""
    today = today or date.today()
    original = (text or "").strip()
    clean = preprocess(original)
    tokens = tokenize(clean)
    filtered = remove_stop_words(tokens)

    label, conf, method = classify_reason(original)
    dt, dt_phrase = extract_date(original, today)
    times = extract_times(original)
    dest, dest_method = extract_destination(original, label)
    priority, prio_reason = suggest_priority(original, label, dt, today)

    info = {
        "original_text": original,
        "cleaned_text": clean,
        "tokens": tokens,
        "filtered_tokens": filtered,
        "category": label,
        "confidence": round(conf, 3),
        "classification_method": method,
        "destination": dest,
        "destination_method": dest_method,
        "departure_date": dt.isoformat() if dt else None,
        "date_phrase": dt_phrase,
        "departure_time": times["departure"],
        "return_time": times["return"],
        "priority": priority,
        "priority_reason": prio_reason,
        "entities": extract_entities(original),
    }
    info["missing"] = detect_missing(info)
    info["is_valid"] = len(tokens) >= 3
    # past-date check
    info["date_in_past"] = bool(dt and dt < today)
    return info


def model_status():
    _get_model()
    return _model_status


if __name__ == "__main__":
    import json
    demo = ("I need permission to visit the hospital tomorrow because I am "
            "not feeling well. I will return by 6 PM.")
    print(json.dumps(analyze_request(demo), indent=2))
