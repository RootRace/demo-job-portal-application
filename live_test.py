import requests

session = requests.Session()
BASE_URL = "http://localhost:5000"

print("--- Live Test: Job Portal Sprint 3 ---")

#---------------------------------------------------------
# Test 1: Admin Dashboard and Vetting Criteria Updating
#---------------------------------------------------------
print("1. Admin Login...")
res = session.post(f"{BASE_URL}/admin/login", data={"email": "admin@test.com", "password": "password123"})
if "Dashboard" in res.text or res.status_code == 200:
    print("   ✅ Admin Login successful")
else:
    print("   ❌ Admin Login failed")

#---------------------------------------------------------
# Test 2: Recruiter Login & Application Filtering (PBI-17)
#---------------------------------------------------------
session.get(f"{BASE_URL}/logout") # Logout admin
print("\n2. Recruiter Login & Filtering...")
res = session.post(f"{BASE_URL}/login", data={"email": "recruiter@test.com", "password": "password123"})

filter_res = session.get(f"{BASE_URL}/recruiter/applications/1/filter?skill=python")
if filter_res.status_code == 200 and isinstance(filter_res.json(), list):
    print(f"   ✅ Filter endpoint (PBI-17) returned {len(filter_res.json())} candidate(s)")
else:
    print("   ❌ Filter endpoint failed")

#---------------------------------------------------------
# Test 3: Updating Application Status (PBI-19 Setup)
#---------------------------------------------------------
print("\n3. Recruiter Application Status Update...")
update_res = session.post(f"{BASE_URL}/recruiter/update-application-status", 
    data={"application_id": 1, "status": "shortlisted"},
    headers={"Referer": f"{BASE_URL}/recruiter/dashboard"}
)
if update_res.status_code == 200:
    print("   ✅ Status updated to 'shortlisted'")
else:
    print("   ❌ Status update failed")

#---------------------------------------------------------
# Test 4: Candidate Notifications via Polling API (PBI-19)
#---------------------------------------------------------
session.get(f"{BASE_URL}/logout") # Logout recruiter
print("\n4. Candidate Login & Notification Polling...")
session.post(f"{BASE_URL}/login", data={"email": "candidate@test.com", "password": "password123"})

notif_res = session.get(f"{BASE_URL}/api/notifications")
if notif_res.status_code == 200:
    data = notif_res.json()
    if data.get("unread_count", data.get("count", 0)) > 0:
        notifs = data.get("notifications", [])
        if notifs:
            msg = notifs[0].get("message", "No msg")
            print(f"   ✅ Notifications (PBI-19) active! Unread: {data.get('unread_count')}. Msg: '{msg}'")
        else:
            print("   ✅ Notifications active but empty list")
    else:
        print("   ❌ Notifications check returned 0 unread.")
else:
    print(f"   ❌ Notifications endpoint failed: {notif_res.status_code}")

#---------------------------------------------------------
# Test 5: DB Integrity and Indexes (PBI-20)
#---------------------------------------------------------
import sqlite3
print("\n5. Checking DB Indexes (PBI-20)...")
conn = sqlite3.connect("jobs.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='index'")
indexes = [r[0] for r in c.fetchall()]
required_indexes = ['idx_applications_job_id', 'idx_candidate_profiles_user_id']
missing = [idx for idx in required_indexes if idx not in indexes]
if not missing:
    print("   ✅ Analytics indexes are correctly configured in DB")
else:
    print(f"   ❌ Missing indexes: {missing}")

print("\n--- Live Test Complete ---")
