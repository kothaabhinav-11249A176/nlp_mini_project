"""init_db.py - create outpass.db with all tables and demo accounts.
Usage:  python init_db.py          (safe to re-run; existing data is kept)
        python init_db.py --reset  (deletes the old database first)"""
import os, sys
import database as db

if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
        print("Old database deleted.")
    db.init_db()
    print("Database ready:", db.DB_PATH)
    print("  Warden : username 'warden'  password 'Warden@123'")
    print("  Student: ID '21CS001'       password 'Student@123'")
    print("  Student: ID '21EC014'       password 'Student@123'")
