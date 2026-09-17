from tests.conftest import auth_headers


def create_manual_rate(client, headers, name, values: dict):
    r = client.post("/api/reference-rates", json={"name": name, "rate_type": "manual"}, headers=headers)
    rate = r.json()
    for ym, v in values.items():
        client.put(f"/api/reference-rates/{rate['id']}/monthly/{ym}", json={"rate": v}, headers=headers)
    return rate["id"]


def test_add_bond_appears_in_list_test1(client, staff_user):
    headers = auth_headers(staff_user)
    r = client.post("/api/bonds", json={"code": "VHML12617"}, headers=headers)
    assert r.status_code == 201, r.text
    listing = client.get("/api/bonds", headers=headers).json()
    assert any(b["code"] == "VHML12617" for b in listing)


def test_duplicate_bond_code_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    client.post("/api/bonds", json={"code": "DUPBOND"}, headers=headers)
    r = client.post("/api/bonds", json={"code": "DUPBOND"}, headers=headers)
    assert r.status_code == 422


def test_holding_and_outstanding_test2_test3(client, staff_user):
    headers = auth_headers(staff_user)
    bond = client.post("/api/bonds", json={"code": "HLD01"}, headers=headers).json()
    client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "HLD01", "issue_date": "2025-10-01", "maturity_date": "2030-10-01", "pay_freq_months": 3, "par_value": 100, "version": bond["version"]},
        headers=headers,
    )
    r = client.put(
        f"/api/bonds/{bond['id']}/monthly/2025-11",
        json={"advised_volume": 2000, "buyback_volume": -500, "invested_volume": 100, "sold_volume": -20},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    computed = client.get(f"/api/bonds/{bond['id']}/computed", params={"start": "2025-11", "end": "2025-11"}, headers=headers).json()
    assert computed[0]["outstanding"] == 1500
    assert computed[0]["holding"] == 80


def test_fixed_and_floating_coupon_test4_test5_test9(client, staff_user):
    headers = auth_headers(staff_user)
    rate_id = create_manual_rate(client, headers, "TPB 12M", {"2025-11": 5.5})

    bond = client.post("/api/bonds", json={"code": "CPN01"}, headers=headers).json()
    b = client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "CPN01", "issue_date": "2025-10-01", "maturity_date": "2030-10-01", "pay_freq_months": 3, "par_value": 100, "version": bond["version"]},
        headers=headers,
    ).json()

    ic = b["interest_config"]
    r = client.patch(
        f"/api/bonds/{bond['id']}/interest-config",
        json={"rate_type": "floating", "spread": 6, "reference_rate_id": rate_id, "version": ic["version"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    computed = client.get(f"/api/bonds/{bond['id']}/computed", params={"start": "2025-11", "end": "2025-11"}, headers=headers).json()
    assert computed[0]["coupon"] == 11.5  # test5: 5.5 + 6

    # test9: Control link — bumping TPB's rate must change the bond's coupon
    # without touching the bond itself.
    rates = client.get("/api/reference-rates", headers=headers).json()
    tpb = next(r for r in rates if r["id"] == rate_id)
    cell_version = tpb["monthly_values"]["2025-11"]["version"]
    client.put(f"/api/reference-rates/{rate_id}/monthly/2025-11", json={"rate": 6.0, "version": cell_version}, headers=headers)
    computed2 = client.get(f"/api/bonds/{bond['id']}/computed", params={"start": "2025-11", "end": "2025-11"}, headers=headers).json()
    assert computed2[0]["coupon"] == 12.0  # 6.0 + 6


def test_rename_bond_preserves_data_test12(client, staff_user):
    headers = auth_headers(staff_user)
    bond = client.post("/api/bonds", json={"code": "REN01"}, headers=headers).json()
    client.put(f"/api/bonds/{bond['id']}/monthly/2025-11", json={"advised_volume": 500}, headers=headers)

    fresh = client.get(f"/api/bonds/{bond['id']}", headers=headers).json()
    r = client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "REN01_NEW", "pay_freq_months": 3, "par_value": 100, "version": fresh["version"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "REN01_NEW"
    assert r.json()["monthly_data"]["2025-11"]["advised_volume"] == 500


def test_multi_user_conflict_test13(client, staff_user):
    headers = auth_headers(staff_user)
    bond = client.post("/api/bonds", json={"code": "CONF01"}, headers=headers).json()
    # user A and B both fetch version 1
    a_version = bond["version"]
    ok = client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "CONF01_A", "pay_freq_months": 3, "par_value": 100, "version": a_version},
        headers=headers,
    )
    assert ok.status_code == 200
    stale = client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "CONF01_B", "pay_freq_months": 3, "par_value": 100, "version": a_version},
        headers=headers,
    )
    assert stale.status_code == 409
    assert "thay đổi bởi người dùng khác" in stale.json()["message"]


def test_maturity_before_issue_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    bond = client.post("/api/bonds", json={"code": "DATEBAD"}, headers=headers).json()
    r = client.patch(
        f"/api/bonds/{bond['id']}",
        json={"code": "DATEBAD", "issue_date": "2026-01-01", "maturity_date": "2025-01-01", "pay_freq_months": 3, "par_value": 100, "version": bond["version"]},
        headers=headers,
    )
    assert r.status_code == 422


def test_viewer_cannot_create_bond(client, db_session):
    from tests.conftest import make_user

    viewer = make_user(db_session, "viewer2@tps.vn", "Viewer")
    headers = auth_headers(viewer)
    r = client.post("/api/bonds", json={"code": "NOPE"}, headers=headers)
    assert r.status_code == 403


def test_soft_delete_and_restore(client, staff_user, db_session):
    from tests.conftest import make_user

    manager = make_user(db_session, "mgr@tps.vn", "Manager")
    headers_staff = auth_headers(staff_user)
    headers_mgr = auth_headers(manager)
    bond = client.post("/api/bonds", json={"code": "DEL01"}, headers=headers_staff).json()

    r = client.delete(f"/api/bonds/{bond['id']}", headers=headers_mgr)
    assert r.status_code == 200
    listing = client.get("/api/bonds", headers=headers_staff).json()
    assert not any(b["code"] == "DEL01" for b in listing)

    r = client.post(f"/api/bonds/{bond['id']}/restore", headers=headers_mgr)
    assert r.status_code == 200
    listing = client.get("/api/bonds", headers=headers_staff).json()
    assert any(b["code"] == "DEL01" for b in listing)
