"""
train_model.py - reproducible training script for the reason classifier.

Run:   python train_model.py
Reads  data/training_data.csv  (120 hand-written sample requests, 6 classes)
Writes data/reason_model.joblib  and  data/training_report.txt

Model: TF-IDF (unigrams + bigrams) -> Multinomial Naive Bayes.
The accuracy printed is 5-fold cross-validation on the SAME small dataset,
so treat it as a rough indicator, not a production-grade benchmark.
"""
import os
from nlp_processing import train_model, BASE_DIR

if __name__ == "__main__":
    model, report = train_model(save=True)
    text = ("Training samples      : %d\n"
            "5-fold CV accuracy   : %.3f (+/- %.3f)\n"
            "Saved model          : data/reason_model.joblib\n"
            % (report["samples"], report["cv_accuracy_mean"], report["cv_accuracy_std"]))
    print(text)
    with open(os.path.join(BASE_DIR, "data", "training_report.txt"), "w") as f:
        f.write(text)
