"""Captures genuine screenshots from the running app (needs: pip install playwright; playwright install chromium)."""
from playwright.sync_api import sync_playwright
OUT = "docs/screenshots/"
B = "http://127.0.0.1:5000"
MSG = "I need permission to visit the hospital tomorrow because I am not feeling well. I will return by 6 PM."
with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    def shot(name, full=True):
        pg.wait_for_load_state("networkidle"); pg.screenshot(path=OUT + name + ".png", full_page=full); print("saved", name)
    pg.goto(B + "/"); shot("01_home")
    pg.goto(B + "/register"); shot("02_student_register")
    pg.goto(B + "/login"); shot("03_student_login")
    pg.fill("[name=identifier]", "21CS001"); pg.fill("[name=password]", "Student@123"); pg.click("button.btn-primary")
    shot("04_student_dashboard")
    pg.goto(B + "/student/profile"); shot("05_student_profile")
    pg.goto(B + "/student/request"); pg.fill("#message", MSG); shot("06_request_form")
    pg.click("text=Analyze with NLP"); shot("07_nlp_analysis")
    pg.click("text=Submit to Warden"); shot("08_request_status")
    pg.goto(B + "/student/requests"); shot("09_my_requests")
    # approved outpass (student view)
    pg.goto(B + "/student/requests?status=Approved"); pg.click("text=Details >> nth=0"); pg.click("text=View Digital Outpass"); shot("14_student_outpass_page")
    pg.click("form button:has-text('Logout')")
    pg.goto(B + "/warden/login"); shot("10_warden_login")
    pg.fill("[name=username]", "warden"); pg.fill("[name=password]", "Warden@123"); pg.click("button.btn-dark")
    shot("11_warden_dashboard")
    pg.goto(B + "/warden/dashboard?status=Pending"); pg.click("text=Review >> nth=-1"); shot("12_warden_review")
    pg.fill("[name=remarks]", "Approved. Return before 6 PM."); pg.click("button:has-text('Approve')"); shot("13_after_approval")
    pg.click("text=Open Digital Outpass"); shot("15_warden_outpass_page")
    br.close()
