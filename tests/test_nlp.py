"""Unit tests for nlp_processing.py  -  run:  python -m unittest discover -s tests -v"""
import os, sys, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nlp_processing as nlp

TODAY = date(2026, 11, 2)   # a Monday - fixed so tests are reproducible


class TestNLP(unittest.TestCase):
    def test_example_from_brief(self):
        r = nlp.analyze_request("I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM.", TODAY)
        self.assertEqual(r["category"], "Medical")
        self.assertEqual(r["destination"], "Hospital")
        self.assertEqual(r["departure_date"], "2026-11-03")
        self.assertEqual(r["return_time"], "18:00")
        self.assertEqual(r["priority"], "High")
        self.assertEqual(r["missing"], [])

    def test_preprocess_and_tokens(self):
        clean = nlp.preprocess("  Going to the BANK!!  ")
        self.assertEqual(clean, "going to the bank")
        toks = nlp.tokenize(clean)
        self.assertEqual(toks, ["going", "to", "the", "bank"])
        self.assertEqual(nlp.remove_stop_words(toks), ["bank"])

    def test_categories(self):
        cases = {
            "I have to attend my cousin's wedding on Saturday": "Family Function",
            "I want to go to the mall for shopping this evening": "Shopping",
            "I have a placement interview on Monday": "Academic",
            "I need to go to the bank to open an account": "Personal Work",
            "I want to watch a movie with friends": "Other",
        }
        for text, expected in cases.items():
            self.assertEqual(nlp.classify_reason(text)[0], expected, text)

    def test_dates(self):
        d = lambda t: nlp.extract_date(t, TODAY)[0]
        self.assertEqual(d("I will go today"), TODAY)
        self.assertEqual(d("going tomorrow"), date(2026, 11, 3))
        self.assertEqual(d("day after tomorrow"), date(2026, 11, 4))
        self.assertEqual(d("on Friday"), date(2026, 11, 6))
        self.assertEqual(d("on 15 November"), date(2026, 11, 15))
        self.assertEqual(d("on 15th nov 2026"), date(2026, 11, 15))
        self.assertEqual(d("on 20/11/2026"), date(2026, 11, 20))
        self.assertEqual(d("on Nov 9"), date(2026, 11, 9))
        self.assertEqual(d("in 3 days"), date(2026, 11, 5))
        self.assertEqual(d("on 5 January"), date(2027, 1, 5))   # rolls to next year
        self.assertIsNone(d("sometime soon"))

    def test_times(self):
        t = nlp.extract_times
        self.assertEqual(t("I will return by 6 PM")["return"], "18:00")
        self.assertEqual(t("back by 8:30 pm")["return"], "20:30")
        self.assertEqual(t("return before 18:00")["return"], "18:00")
        self.assertEqual(t("leave at 9 am and return by 5 pm"), {"departure": "09:00", "return": "17:00"})
        self.assertEqual(t("will be back by evening")["return"], "18:00")
        self.assertIsNone(t("no time here")["return"])

    def test_destination(self):
        self.assertEqual(nlp.extract_destination("visit Apollo Hospital tomorrow")[0], "Apollo Hospital")
        self.assertEqual(nlp.extract_destination("go to the bank")[0], "Bank")
        self.assertEqual(nlp.extract_destination("going to the railway station")[0], "Railway Station")
        self.assertEqual(nlp.extract_destination("going to Gandhipuram tomorrow")[0], "Gandhipuram")
        self.assertIsNone(nlp.extract_destination("I want permission please")[0])

    def test_missing_information(self):
        r = nlp.analyze_request("I want to go out", TODAY)
        self.assertIn("Date of leaving", r["missing"])
        self.assertIn("Expected return time", r["missing"])
        self.assertIn("Destination", r["missing"])
        full = nlp.analyze_request("Going to the mall tomorrow, back by 7 pm for shopping", TODAY)
        self.assertEqual(full["missing"], [])

    def test_priority(self):
        self.assertEqual(nlp.suggest_priority("urgent emergency", "Other")[0], "High")
        self.assertEqual(nlp.suggest_priority("buy clothes", "Shopping")[0], "Low")
        self.assertEqual(nlp.suggest_priority("wedding", "Family Function")[0], "Medium")

    def test_ml_model_trains_and_predicts(self):
        model, rep = nlp.train_model(save=False)
        self.assertGreaterEqual(rep["samples"], 100)
        self.assertEqual(model.predict([nlp.preprocess("doctor appointment at the hospital")])[0], "Medical")


if __name__ == "__main__":
    unittest.main()
