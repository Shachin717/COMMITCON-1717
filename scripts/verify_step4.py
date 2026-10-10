#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
import http.cookiejar

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

USERS = {
    "ADMIN": ("admin@git.edu", "Admin@123"),
    "COORDINATOR": ("coordinator.block_a@git.edu", "Coord@123"),
    "FACULTY": ("faculty.cse@git.edu", "Faculty@123"),
    "HOD": ("hod.cse@git.edu", "Hod@123"),
}

PORTALS = ["admin", "coordinator", "faculty", "hod"]

def post_json(url, data, headers=None):
    headers = headers or {}
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers

def get_url(url, headers=None, follow_redirects=False):
    headers = headers or {}
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not follow_redirects:
                return None
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with opener.open(req) as resp:
            return resp.status, resp.geturl(), resp.headers
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        return e.code, loc, e.headers

def run_tests():
    print("=" * 60)
    print("TEST 1: 4x4 ROLE x LOGIN PORTAL MATRIX")
    print("=" * 60)
    login_tokens = {}
    login_cookies = {}

    for user_role, (email, pw) in USERS.items():
        for portal in PORTALS:
            url = f"{BACKEND_URL}/api/auth/{portal}/login"
            status, body, headers = post_json(url, {"email": email, "password": pw})
            expected = 200 if user_role.lower() == portal else 401
            passed = (status == expected)
            print(f"[{'PASS' if passed else 'FAIL'}] {user_role:<11} on /{portal}/login -> HTTP {status} (expected {expected})")
            if user_role.lower() == portal and status == 200:
                data = json.loads(body)
                login_tokens[user_role] = data["access_token"]
                # parse cookies from headers
                set_cookies = headers.get_all("Set-Cookie") or []
                cookie_str = "; ".join([c.split(";")[0] for c in set_cookies])
                login_cookies[user_role] = cookie_str

    print("\n" + "=" * 60)
    print("TEST 2: ROLE x ENDPOINT-GROUP AUTHORIZATION MATRIX")
    print("=" * 60)
    endpoints = {
        "/api/admin/users": "ADMIN",
        "/api/coordinator/blocks": "COORDINATOR",
        "/api/faculty/bookings": "FACULTY",
        "/api/hod/summary": "HOD",
    }
    for user_role, token in login_tokens.items():
        for endpoint, allowed_role in endpoints.items():
            req_url = f"{BACKEND_URL}{endpoint}"
            headers = {"Authorization": f"Bearer {token}"}
            status, _, _ = get_url(req_url, headers=headers)
            expected = 200 if user_role == allowed_role else 403
            passed = (status == expected)
            print(f"[{'PASS' if passed else 'FAIL'}] {user_role:<11} calling {endpoint:<24} -> HTTP {status} (expected {expected})")

    print("\n" + "=" * 60)
    print("TEST 3: FRONTEND MIDDLEWARE ROUTE PROTECTION & REDIRECTS")
    print("=" * 60)
    
    # 3a. Unauthenticated access
    for area in ["admin", "coordinator", "faculty", "hod"]:
        status, loc, _ = get_url(f"{FRONTEND_URL}/{area}", follow_redirects=False)
        expected_loc = f"/{area}/login"
        passed = (status == 307 or status == 302 or status == 303) and expected_loc in str(loc)
        print(f"[{'PASS' if passed else 'FAIL'}] Unauthenticated /{area:<11} -> HTTP {status} Redirect: {loc}")

    # 3b. Authenticated role opening portals & login pages
    test_cases = [
        ("COORDINATOR", "/admin", "/coordinator?unauthorized=1"),
        ("COORDINATOR", "/faculty", "/coordinator?unauthorized=1"),
        ("COORDINATOR", "/hod", "/coordinator?unauthorized=1"),
        ("COORDINATOR", "/admin/login", "/coordinator"),
        ("COORDINATOR", "/coordinator/login", "/coordinator"),
        ("COORDINATOR", "/coordinator", None),  # 200 OK
        ("ADMIN", "/coordinator", "/admin?unauthorized=1"),
        ("ADMIN", "/faculty", "/admin?unauthorized=1"),
        ("ADMIN", "/hod", "/admin?unauthorized=1"),
        ("ADMIN", "/coordinator/login", "/admin"),
        ("ADMIN", "/admin", None),  # 200 OK
        ("FACULTY", "/admin", "/faculty?unauthorized=1"),
        ("FACULTY", "/coordinator", "/faculty?unauthorized=1"),
        ("FACULTY", "/hod", "/faculty?unauthorized=1"),
        ("FACULTY", "/faculty", None),  # 200 OK
        ("HOD", "/admin", "/hod?unauthorized=1"),
        ("HOD", "/coordinator", "/hod?unauthorized=1"),
        ("HOD", "/faculty", "/hod?unauthorized=1"),
        ("HOD", "/hod", None),  # 200 OK
    ]

    for role, path, expected_redirect in test_cases:
        token = login_tokens[role]
        cookie_header = f"access_token={token}; user_role={role}"
        headers = {"Cookie": cookie_header}
        status, loc, _ = get_url(f"{FRONTEND_URL}{path}", headers=headers, follow_redirects=False)
        if expected_redirect is None:
            passed = (status == 200)
            print(f"[{'PASS' if passed else 'FAIL'}] {role:<11} on {path:<18} -> HTTP {status} OK (Allowed)")
        else:
            passed = (status in [302, 303, 307] and str(loc).endswith(expected_redirect))
            print(f"[{'PASS' if passed else 'FAIL'}] {role:<11} on {path:<18} -> HTTP {status} Redirect: {loc}")

if __name__ == "__main__":
    run_tests()
