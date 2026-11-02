# Test Cases and Results

Automated results come from `python -m unittest discover -s tests -v` (19 tests, run in the build environment on Linux / Python 3.12).
**Not tested:** the app has not been run on a Windows 11 machine by the author of this package - the commands in the README are standard
cross-platform Python commands, but you should run the test command yourself on your laptop to confirm.

| ID | Scenario | Input / Steps | Expected result | Test |
|---|---|---|---|---|
| T01 | Student registration | Valid form | Redirect to login, password stored hashed | test_01_registration |
| T02 | Duplicate / weak registration | Same ID; password `abc`; phone `12` | HTTP 400 with error messages | test_01_registration |
| T03 | Student login | 21CS001 / Student@123 | Dashboard opens | test_02 |
| T04 | Invalid login | Wrong password / unknown user | HTTP 401, error message | test_02, test_10 |
| T05 | CSRF protection | POST without token | HTTP 400 | test_03 |
| T06 | NL request submission | Hospital sentence | Analysis page shows Medical, Hospital | test_04 |
| T07 | Too-short message | `hi` | Rejected with message | test_04 |
| T08 | Reason classification | 5 sample sentences | Correct category for each | test_categories |
| T09 | Date extraction | today, tomorrow, weekday, 15 November, dd/mm/yyyy, in 3 days, next-year rollover | Correct dates (fixed "today") | test_dates |
| T10 | Time extraction | 6 PM, 8:30 pm, 18:00, evening, leave+return | Correct HH:MM | test_times |
| T11 | Destination extraction | Apollo Hospital, bank, railway station, unknown place | Correct / None | test_destination |
| T12 | Missing-information detection | "I want to go out" | Destination, date, return time flagged | test_missing_information |
| T13 | Warden login | warden / Warden@123 | Warden dashboard; bad password gives 401 | test_05, test_09 |
| T14 | Request approval | Warden approves | Status Approved, outpass number, 2 history rows | test_05 |
| T15 | Rejection | Empty remark blocked; remark then rejects, no outpass number | Status Rejected | test_06 |
| T16 | Double decision | Approve then reject same request | Second ignored | test_05 |
| T17 | Duplicate request | Same student, same date | HTTP 400 | test_05 |
| T18 | Invalid inputs | Past date, empty destination, bad time | HTTP 400 | test_07 |
| T19 | Unauthorized access | Anonymous / student open warden pages or approve | Redirect / 403 | test_08 |
| T20 | Other student's data | Student B opens student A's request or PDF | 404 / 403 | test_05 |
| T21 | PDF generation | Approved request | `%PDF` file > 3 KB; unavailable before approval | test_05 |
| T22 | QR generation | Approved request | PNG image; verify link valid, tampered link invalid | test_05 |
| T23 | SQL injection attempt | `' OR '1'='1` as login | 401, no access | test_10 |
| T24 | ML model trains | Train from CSV | Model trains, predicts Medical for doctor sentence | test_ml_model_trains_and_predicts |
