import io

from conftest import participant_payload


def create_participant(client, headers, **kw):
    res = client.post("/api/participants", headers=headers, json=participant_payload(**kw))
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def create_measure(client, headers, location_id=1, **kw):
    body = {"name": "Aktivcenter Minden", "location_id": location_id, "status": "aktiv",
            "start_date": "01.01.2026", "end_date": "2026-12-31", "capacity": 2, **kw}
    res = client.post("/api/measures", headers=headers, json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


# ---------- Health / Config ----------

def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok" and body["app"] == "qualli-erp"


def test_field_config(client, admin_headers):
    cfg = client.get("/api/participants/config/fields", headers=admin_headers).get_json()
    ids = [s["id"] for s in cfg["sections"]]
    assert ids == ["basic", "address", "characteristics"]
    assert all("aliases" not in f for s in cfg["sections"] for f in s["fields"])


def test_unknown_api_route_returns_json_404(client):
    res = client.get("/api/gibtsnicht")
    assert res.status_code == 404 and "error" in res.get_json()


# ---------- Participants ----------

def test_participant_crud_with_audit_trail(client, admin_headers):
    p = create_participant(client, admin_headers)
    assert p["basic_info"]["birth_date"] == "1990-02-01"
    assert p["basic_info"]["gender"] == "m"
    assert p["characteristics"]["driving_license"] == ["B", "BE"]
    assert p["location_name"] == "Minden"

    res = client.put(f"/api/participants/{p['id']}", headers=admin_headers,
                     json={"basic_info": {"phone": "0571 123"}, "address_info": {"street": ""}})
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["basic_info"]["phone"] == "0571 123"
    assert updated["basic_info"]["first_name"] == "Max"  # Rest bleibt erhalten
    assert "street" not in updated["address_info"]

    history = client.get(f"/api/participants/{p['id']}/history", headers=admin_headers).get_json()["items"]
    assert [h["action"] for h in history] == ["update", "create"]
    assert history[0]["changes"]["basic_info"]["phone"] == {"old": None, "new": "0571 123"}
    assert history[0]["changed_by_name"] == "admin"

    assert client.delete(f"/api/participants/{p['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/participants/{p['id']}", headers=admin_headers).status_code == 404
    listing = client.get("/api/participants", headers=admin_headers).get_json()
    assert listing["total"] == 0

    restored = client.post(f"/api/participants/{p['id']}/restore", headers=admin_headers)
    assert restored.status_code == 200 and restored.get_json()["is_deleted"] is False


def test_participant_validation_error(client, admin_headers):
    res = client.post("/api/participants", headers=admin_headers,
                      json={"location_id": 1, "basic_info": {"first_name": "Nur"}})
    assert res.status_code == 422
    assert "basic_info.last_name" in res.get_json()["details"]


def test_participant_duplicate_check(client, admin_headers):
    create_participant(client, admin_headers)
    res = client.post("/api/participants", headers=admin_headers, json=participant_payload())
    assert res.status_code == 409
    assert res.get_json()["details"]["duplicates"][0]["display_name"] == "Mustermann, Max"
    forced = client.post("/api/participants", headers=admin_headers, json=participant_payload(force=True))
    assert forced.status_code == 201


def test_participant_search_and_pagination(client, admin_headers):
    for i in range(30):
        create_participant(client, admin_headers, first=f"Person{i:02d}", last="Test")
    create_participant(client, admin_headers, first="Erika", last="Sonderfall")

    page2 = client.get("/api/participants?per_page=10&page=2&sort=first_name", headers=admin_headers).get_json()
    assert page2["total"] == 31 and page2["pages"] == 4 and len(page2["items"]) == 10
    assert page2["items"][0]["basic_info"]["first_name"] == "Person09"  # "Erika" steht auf Seite 1 vorn

    found = client.get("/api/participants?search=sonder erika", headers=admin_headers).get_json()
    assert found["total"] == 1


def test_participant_location_filter(client, admin_headers, locations):
    create_participant(client, admin_headers, location_id=locations[0].id)
    create_participant(client, admin_headers, first="Anna", location_id=locations[1].id)
    res = client.get(f"/api/participants?location_id={locations[1].id}", headers=admin_headers).get_json()
    assert res["total"] == 1 and res["items"][0]["basic_info"]["first_name"] == "Anna"


# ---------- Standort-Zugriffskontrolle ----------

def test_employee_sees_only_own_location(client, admin_headers, user_headers, locations):
    minden, luebbecke = locations[0], locations[1]
    create_participant(client, admin_headers, first="Minden", location_id=minden.id)
    other = create_participant(client, admin_headers, first="Luebbecke", location_id=luebbecke.id)

    headers = user_headers("ma.minden", "employee", minden)
    listing = client.get("/api/participants", headers=headers).get_json()
    assert [p["basic_info"]["first_name"] for p in listing["items"]] == ["Minden"]

    assert client.get(f"/api/participants/{other['id']}", headers=headers).status_code == 403
    assert client.put(f"/api/participants/{other['id']}", headers=headers, json={}).status_code == 403
    assert client.delete(f"/api/participants/{other['id']}", headers=headers).status_code == 403
    assert client.get(f"/api/participants?location_id={luebbecke.id}", headers=headers).status_code == 403
    res = client.post("/api/participants", headers=headers, json=participant_payload(first="X", location_id=luebbecke.id))
    assert res.status_code == 403

    # Ohne location_id wird der eigene Standort verwendet
    payload = participant_payload(first="Eigen")
    payload.pop("location_id")
    res = client.post("/api/participants", headers=headers, json=payload)
    assert res.status_code == 201 and res.get_json()["location_id"] == minden.id


def test_location_manager_sees_assigned_locations(client, admin_headers, user_headers, locations):
    for loc in locations[:3]:
        create_participant(client, admin_headers, first=f"P{loc.id}", location_id=loc.id)
    headers = user_headers("leitung", "location_manager", locations[0], extra=[locations[1]])
    listing = client.get("/api/participants", headers=headers).get_json()
    assert listing["total"] == 2
    stats = client.get("/api/dashboard/stats", headers=headers).get_json()
    assert stats["participants_total"] == 2 and stats["locations"] == 2
    locs = client.get("/api/dashboard/locations", headers=headers).get_json()["items"]
    assert {l["id"] for l in locs} == {locations[0].id, locations[1].id}


def test_employee_cannot_manage_measures(client, user_headers, locations):
    headers = user_headers("ma2", "employee", locations[0])
    res = client.post("/api/measures", headers=headers, json={"name": "X", "location_id": locations[0].id})
    assert res.status_code == 403


# ---------- Measures ----------

def test_measure_crud_and_status_filter(client, admin_headers):
    m = create_measure(client, admin_headers)
    assert m["start_date"] == "2026-01-01" and m["active_enrollments"] == 0
    create_measure(client, admin_headers, name="Geplant", status="geplant")

    active = client.get("/api/measures?status=aktiv", headers=admin_headers).get_json()
    assert active["total"] == 1 and active["items"][0]["name"] == "Aktivcenter Minden"

    res = client.put(f"/api/measures/{m['id']}", headers=admin_headers, json={"status": "beendet"})
    assert res.get_json()["status"] == "beendet"
    assert client.put(f"/api/measures/{m['id']}", headers=admin_headers, json={"status": "kaputt"}).status_code == 400
    bad = client.put(f"/api/measures/{m['id']}", headers=admin_headers, json={"end_date": "01.01.2020"})
    assert bad.status_code == 422

    assert client.delete(f"/api/measures/{m['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/measures/{m['id']}", headers=admin_headers).status_code == 404


# ---------- Enrollments ----------

def test_enrollment_lifecycle(client, admin_headers):
    p = create_participant(client, admin_headers)
    m = create_measure(client, admin_headers)

    res = client.post("/api/enrollments", headers=admin_headers,
                      json={"participant_id": p["id"], "measure_id": m["id"], "enrollment_date": "15.01.2026"})
    assert res.status_code == 201
    e = res.get_json()
    assert e["status"] == "aktiv" and e["enrollment_date"] == "2026-01-15"

    dup = client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p["id"], "measure_id": m["id"]})
    assert dup.status_code == 409

    by_participant = client.get(f"/api/participants/{p['id']}/enrollments", headers=admin_headers).get_json()["items"]
    assert len(by_participant) == 1 and by_participant[0]["measure_name"] == "Aktivcenter Minden"
    assert client.get(f"/api/enrollments?participant_id={p['id']}", headers=admin_headers).get_json()["total"] == 1

    res = client.put(f"/api/enrollments/{e['id']}", headers=admin_headers, json={"status": "abgebrochen"})
    assert res.get_json()["status"] == "abgebrochen" and res.get_json()["exit_date"] is not None

    assert client.delete(f"/api/enrollments/{e['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/enrollments/{e['id']}", headers=admin_headers).status_code == 404


def test_enrollment_capacity_and_finished_measure(client, admin_headers):
    m = create_measure(client, admin_headers, capacity=1)
    p1 = create_participant(client, admin_headers, first="Eins")
    p2 = create_participant(client, admin_headers, first="Zwei")
    assert client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p1["id"], "measure_id": m["id"]}).status_code == 201
    full = client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p2["id"], "measure_id": m["id"]})
    assert full.status_code == 409 and "voll" in full.get_json()["error"]

    done = create_measure(client, admin_headers, name="Alt", status="beendet")
    res = client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p2["id"], "measure_id": done["id"]})
    assert res.status_code == 422


# ---------- Dashboard & Reports ----------

def test_dashboard_stats(client, admin_headers):
    p = create_participant(client, admin_headers)
    m = create_measure(client, admin_headers)
    client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p["id"], "measure_id": m["id"]})
    stats = client.get("/api/dashboard/stats", headers=admin_headers).get_json()
    assert stats["participants_total"] == 1
    assert stats["measures_by_status"]["aktiv"] == 1
    assert stats["enrollments_by_status"]["aktiv"] == 1
    assert stats["participants_in_active_measure"] == 1


def test_reports(client, admin_headers):
    p = create_participant(client, admin_headers, first="=HYPERLINK")
    m = create_measure(client, admin_headers)
    client.post("/api/enrollments", headers=admin_headers, json={"participant_id": p["id"], "measure_id": m["id"]})

    res = client.get("/api/reports/participants-export", headers=admin_headers)
    assert res.status_code == 200 and res.mimetype == "text/csv"
    text = res.get_data(as_text=True)
    assert text.startswith("﻿ID;Standort;Anrede;Vorname")
    assert "'=HYPERLINK" in text  # Formel-Injection entschärft
    assert "männlich" in text  # Label statt interner Wert

    summary = client.get("/api/reports/measures-summary", headers=admin_headers).get_json()["items"]
    assert summary[0]["enrollments_active"] == 1 and summary[0]["utilization"] == 50.0
    assert client.get("/api/reports/measures-summary?format=csv", headers=admin_headers).mimetype == "text/csv"

    by_loc = client.get("/api/reports/enrollments-by-location", headers=admin_headers).get_json()["items"]
    minden = next(i for i in by_loc if i["location_name"] == "Minden")
    assert minden["aktiv"] == 1


# ---------- Import / Batch ----------

QUALLI_CSV = (
    "Nachname;Vorname;Geburtsdatum;Geschlecht;Straße;PLZ;Ort;Standort;Führerschein;Lieblingsfarbe\n"
    "Schmidt;Anna;03.04.1985;weiblich;Hauptstr. 5;32312;Lübbecke;Lübbecke;B;blau\n"
    "Yilmaz;Mehmet;1990-07-11;männlich;Bahnhofstr. 1;32423;Minden;;B, CE;\n"
    "Schmidt;Anna;03.04.1985;weiblich;Hauptstr. 5;32312;Lübbecke;Lübbecke;B;\n"
    ";Ohne;;;;;;;;\n"
    "Kaputt;Datum;31.31.1999;unbekannt;;;;;;\n"
)


def upload(client, headers, content, **form):
    data = {"file": (io.BytesIO(content.encode("cp1252")), "export.csv"), **form}
    return client.post("/api/import/qualli-life", headers=headers, data=data, content_type="multipart/form-data")


def test_qualli_import_dry_run_and_real(client, admin_headers, locations):
    res = upload(client, admin_headers, QUALLI_CSV, location_id=str(locations[0].id), dry_run="1")
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["dry_run"] is True
    assert body["created"] == 3
    assert body["column_mapping"]["Nachname"] == "basic_info.last_name"
    assert body["column_mapping"]["Standort"] == "location"
    assert "Lieblingsfarbe" in body["unmapped_columns"]
    assert [d["row"] for d in body["duplicates"]] == [4]
    assert [e["row"] for e in body["errors"]] == [5]
    assert [w["row"] for w in body["warnings"]] == [6]
    assert client.get("/api/participants", headers=admin_headers).get_json()["total"] == 0

    res = upload(client, admin_headers, QUALLI_CSV, location_id=str(locations[0].id))
    assert res.status_code == 201 and res.get_json()["created"] == 3
    listing = client.get("/api/participants?search=schmidt", headers=admin_headers).get_json()
    anna = listing["items"][0]
    assert anna["location_name"] == "Lübbecke"
    assert anna["custom_fields"]["import_lieblingsfarbe"] == "blau"
    kaputt = client.get("/api/participants?search=kaputt", headers=admin_headers).get_json()["items"][0]
    assert kaputt["custom_fields"]["import_birth_date"] == "31.31.1999"

    again = upload(client, admin_headers, QUALLI_CSV, location_id=str(locations[0].id)).get_json()
    assert again["created"] == 0 and len(again["duplicates"]) == 4


def test_import_xlsx(client, admin_headers, locations):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Vorname", "Nachname", "Geburtsdatum"])
    import datetime
    ws.append(["Excel", "Person", datetime.datetime(1980, 5, 6)])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    res = client.post("/api/import/qualli-life", headers=admin_headers, content_type="multipart/form-data",
                      data={"file": (buf, "export.xlsx"), "location_id": str(locations[0].id)})
    assert res.status_code == 201, res.get_json()
    p = client.get("/api/participants?search=excel", headers=admin_headers).get_json()["items"][0]
    assert p["basic_info"]["birth_date"] == "1980-05-06"


def test_import_rejects_too_many_rows(client, admin_headers, app):
    app.config["IMPORT_MAX_ROWS"] = 2
    csv_text = "Vorname;Nachname\n" + "".join(f"A{i};B{i}\n" for i in range(3))
    res = upload(client, admin_headers, csv_text, location_id="1")
    assert res.status_code == 400 and "Maximal 2" in res.get_json()["error"]


def test_import_location_access_enforced(client, user_headers, locations):
    headers = user_headers("ma3", "employee", locations[0])
    res = upload(client, headers, "Vorname;Nachname\nA;B\n", location_id=str(locations[1].id))
    assert res.status_code == 403


def test_batch_json(client, admin_headers):
    items = [participant_payload(first=f"B{i}") for i in range(3)]
    res = client.post("/api/participants/batch", headers=admin_headers, json={"participants": items})
    assert res.status_code == 201 and res.get_json()["created"] == 3

    bad = items + [{"location_id": 1, "basic_info": {}}]
    res = client.post("/api/participants/batch", headers=admin_headers, json={"participants": bad})
    assert res.status_code == 422
    assert client.get("/api/participants", headers=admin_headers).get_json()["total"] == 3


def test_admin_user_management(client, admin_headers, locations):
    res = client.post("/api/users", headers=admin_headers, json={
        "username": "leitung.minden", "password": "sicher12345", "role": "location_manager",
        "location_id": locations[0].id, "location_ids": [locations[1].id]})
    assert res.status_code == 201
    assert res.get_json()["location_ids"] == sorted([locations[0].id, locations[1].id])
    no_loc = client.post("/api/users", headers=admin_headers, json={"username": "x", "password": "sicher12345", "role": "employee"})
    assert no_loc.status_code == 422
    assert client.get("/api/users", headers=admin_headers).get_json()["total"] == 2


def test_employees_crud(client, admin_headers, locations):
    res = client.post("/api/employees", headers=admin_headers, json={"name": "Coach A", "location_id": locations[0].id, "start_date": "01.03.2024"})
    assert res.status_code == 201
    emp = res.get_json()
    assert client.get("/api/employees", headers=admin_headers).get_json()["total"] == 1
    assert client.delete(f"/api/employees/{emp['id']}", headers=admin_headers).status_code == 200
    assert client.get("/api/employees", headers=admin_headers).get_json()["total"] == 0
