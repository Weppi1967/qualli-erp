from conftest import auth_header, login


def test_login_success_returns_tokens(client):
    data = login(client)
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "falsch"})
    assert res.status_code == 401
    assert "falsch" in res.get_json()["error"]


def test_login_missing_fields(client):
    assert client.post("/api/auth/login", json={}).status_code == 400


def test_protected_endpoint_requires_token(client):
    res = client.get("/api/participants")
    assert res.status_code == 401
    assert res.get_json()["code"] == "token_missing"


def test_invalid_token_rejected(client):
    res = client.get("/api/participants", headers=auth_header("kaputt"))
    assert res.status_code == 401


def test_me_returns_user_and_locations(client, admin_headers, locations):
    res = client.get("/api/auth/me", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["user"]["username"] == "admin"
    assert len(body["locations"]) == len(locations) >= 6


def test_refresh_issues_new_access_token(client):
    tokens = login(client)
    res = client.post("/api/auth/refresh", headers=auth_header(tokens["refresh_token"]))
    assert res.status_code == 200
    new_token = res.get_json()["access_token"]
    assert client.get("/api/auth/me", headers=auth_header(new_token)).status_code == 200


def test_access_token_cannot_be_used_for_refresh(client):
    tokens = login(client)
    assert client.post("/api/auth/refresh", headers=auth_header(tokens["access_token"])).status_code == 401


def test_logout_revokes_access_and_refresh(client):
    tokens = login(client)
    headers = auth_header(tokens["access_token"])
    res = client.post("/api/auth/logout", headers=headers, json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    assert client.get("/api/auth/me", headers=headers).get_json()["code"] == "token_revoked"
    assert client.post("/api/auth/refresh", headers=auth_header(tokens["refresh_token"])).status_code == 401


def test_deactivated_user_cannot_use_token(client, app, make_user, locations):
    from extensions import db

    user = make_user("weg", "employee", locations[0])
    token = login(client, "weg", "geheim12345")["access_token"]
    user.is_active = False
    db.session.commit()
    assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 401
    assert client.post("/api/auth/login", json={"username": "weg", "password": "geheim12345"}).status_code == 403


def test_change_password(client, admin_headers):
    res = client.post("/api/auth/change-password", headers=admin_headers,
                      json={"current_password": "password123", "new_password": "neuesPasswort1"})
    assert res.status_code == 200
    login(client, "admin", "neuesPasswort1")


def test_non_admin_cannot_manage_users(client, user_headers, locations):
    headers = user_headers("ma", "employee", locations[0])
    assert client.get("/api/users", headers=headers).status_code == 403
