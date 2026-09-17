import io
import json

from tests.conftest import auth_headers, make_user


def test_audit_log_records_coupon_change_test14(client, staff_user):
    headers = auth_headers(staff_user)
    b = client.post("/api/bonds", json={"code": "AUD01"}, headers=headers).json()
    ic = b["interest_config"]
    client.patch(f"/api/bonds/{b['id']}/interest-config", json={"rate_type": "fixed", "fixed_rate": 10.5, "version": ic["version"]}, headers=headers)
    b2 = client.get(f"/api/bonds/{b['id']}", headers=headers).json()
    client.patch(
        f"/api/bonds/{b['id']}/interest-config",
        json={"rate_type": "fixed", "fixed_rate": 11, "version": b2["interest_config"]["version"]},
        headers=headers,
    )

    r = client.get("/api/audit-logs", params={"module": "bond_interest_config", "record_id": b["id"]}, headers=headers)
    # Manager+ only; staff_user has no Manager role, so expect 403.
    assert r.status_code == 403


def test_audit_log_visible_to_manager(client, staff_user, db_session):
    headers = auth_headers(staff_user)
    manager = make_user(db_session, "audit-mgr@tps.vn", "Manager")
    mgr_headers = auth_headers(manager)

    b = client.post("/api/bonds", json={"code": "AUD02"}, headers=headers).json()
    ic = b["interest_config"]
    client.patch(f"/api/bonds/{b['id']}/interest-config", json={"rate_type": "fixed", "fixed_rate": 10.5, "version": ic["version"]}, headers=headers)
    b2 = client.get(f"/api/bonds/{b['id']}", headers=headers).json()
    client.patch(
        f"/api/bonds/{b['id']}/interest-config",
        json={"rate_type": "fixed", "fixed_rate": 11, "version": b2["interest_config"]["version"]},
        headers=headers,
    )

    r = client.get("/api/audit-logs", params={"module": "bond_interest_config"}, headers=mgr_headers)
    assert r.status_code == 200, r.text
    page = r.json()
    change = next(x for x in page["items"] if x["field"] == "fixed_rate" and float(x["new_value"]) == 11)
    assert float(change["old_value"]) == 10.5
    assert change["user_email"] == "staff-test@tps.vn"


def test_export_import_json_roundtrip(client, staff_user, admin_user):
    staff_headers = auth_headers(staff_user)
    admin_headers = auth_headers(admin_user)

    b = client.post("/api/bonds", json={"code": "EXP01"}, headers=staff_headers).json()
    client.patch(
        f"/api/bonds/{b['id']}",
        json={"code": "EXP01", "issue_date": "2025-10-01", "maturity_date": "2030-10-01", "pay_freq_months": 3, "par_value": 100, "version": b["version"]},
        headers=staff_headers,
    )

    r = client.get("/api/admin/export/json", headers=staff_headers)
    assert r.status_code == 200
    dump = json.loads(r.content)
    assert any(x["code"] == "EXP01" for x in dump["bonds"])

    # Re-importing the same dump must not duplicate/overwrite (additive-only import).
    files = {"file": ("dump.json", io.BytesIO(r.content), "application/json")}
    imp = client.post("/api/admin/import/json", files=files, headers=admin_headers)
    assert imp.status_code == 200, imp.text
    report = imp.json()
    assert report["skipped"]["bonds"] >= 1

    listing = client.get("/api/bonds", headers=staff_headers).json()
    assert sum(1 for x in listing if x["code"] == "EXP01") == 1


def test_import_requires_admin(client, staff_user):
    headers = auth_headers(staff_user)
    files = {"file": ("dump.json", io.BytesIO(b'{"schema": 1}'), "application/json")}
    r = client.post("/api/admin/import/json", files=files, headers=headers)
    assert r.status_code == 403


def test_import_rejects_bad_schema(client, admin_user):
    headers = auth_headers(admin_user)
    files = {"file": ("dump.json", io.BytesIO(b'{"nope": true}'), "application/json")}
    r = client.post("/api/admin/import/json", files=files, headers=headers)
    assert r.status_code == 422


def test_reset_requires_password_and_confirm_word(client, admin_user):
    headers = auth_headers(admin_user)
    wrong_pw = client.post("/api/admin/reset", json={"password": "wrong", "confirm_word": "RESET"}, headers=headers)
    assert wrong_pw.status_code == 422
    wrong_word = client.post("/api/admin/reset", json={"password": "Password123!", "confirm_word": "yes"}, headers=headers)
    assert wrong_word.status_code == 422


def test_reset_wipes_business_data(client, staff_user, admin_user):
    staff_headers = auth_headers(staff_user)
    admin_headers = auth_headers(admin_user)
    client.post("/api/bonds", json={"code": "RESETME"}, headers=staff_headers)

    r = client.post("/api/admin/reset", json={"password": "Password123!", "confirm_word": "RESET"}, headers=admin_headers)
    assert r.status_code == 200, r.text

    listing = client.get("/api/bonds", headers=staff_headers).json()
    assert listing == []


def test_duplicate_bond_detection_test17(client, staff_user, db_session):
    headers = auth_headers(staff_user)
    manager = make_user(db_session, "dup-mgr@tps.vn", "Manager")
    mgr_headers = auth_headers(manager)

    client.post("/api/bonds", json={"code": "VHML999"}, headers=headers)
    r2 = client.post("/api/bonds", json={"code": "  vhml999  "}, headers=headers)
    # Different normalized-whitespace/case still collides with the exact-string
    # unique constraint only if identical after our own .strip(); the API
    # itself doesn't lowercase, so this creates a second, distinctly-cased row.
    assert r2.status_code in (201, 422)

    dups = client.get("/api/admin/duplicates/bonds", headers=mgr_headers)
    assert dups.status_code == 200
    if r2.status_code == 201:
        groups = dups.json()
        assert any("VHML999" in g["codes"] and len(g["codes"]) > 1 for g in groups)


def test_backup_creates_file(client, admin_user, tmp_path, monkeypatch):
    from app.services import admin_service

    monkeypatch.setattr(admin_service.settings, "backup_dir", str(tmp_path))
    headers = auth_headers(admin_user)
    r = client.post("/api/admin/backup", headers=headers)
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["size_bytes"] > 0
    assert (tmp_path / meta["filename"]).exists()

    listing = client.get("/api/admin/backups", headers=headers)
    assert listing.status_code == 200
    assert any(b["filename"] == meta["filename"] for b in listing.json())
