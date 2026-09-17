from tests.conftest import auth_headers


def setup_bond(client, headers, code="WK01"):
    b = client.post("/api/bonds", json={"code": code}, headers=headers).json()
    b = client.patch(
        f"/api/bonds/{b['id']}",
        json={"code": code, "issue_date": "2025-10-01", "maturity_date": "2030-10-01", "pay_freq_months": 3, "par_value": 100, "version": b["version"]},
        headers=headers,
    ).json()
    ic = b["interest_config"]
    client.patch(f"/api/bonds/{b['id']}/interest-config", json={"rate_type": "fixed", "fixed_rate": 12, "version": ic["version"]}, headers=headers)
    return client.get(f"/api/bonds/{b['id']}", headers=headers).json()


def test_weekly_accrual_test21(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    r = client.put(f"/api/weekly/2025-11-W2/bonds/{b['id']}", json={"volume": 100}, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    row = next(x for x in data["rows"] if x["bond_id"] == b["id"])
    assert row["coupon"] == 12
    # par=100, vol=100, coupon=12%, days in Nov 2025 = 30 -> par*vol*coupon*days/365
    expected = 100 * 100 * 0.12 * 30 / 365
    assert abs(row["accrual"] - expected) < 1e-9
    assert data["latest_week_with_data"] == "2025-11-W2"


def test_weekly_no_forward_fill_until_carry_forward(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "WK02")
    client.put(f"/api/weekly/2025-11-W1/bonds/{b['id']}", json={"volume": 50}, headers=headers)

    week2 = client.get("/api/weekly/2025-11-W2", headers=headers).json()
    row2 = next(x for x in week2["rows"] if x["bond_id"] == b["id"])
    assert row2["volume"] is None  # not auto-filled

    cf = client.post("/api/weekly/carry-forward", json={"from_week": "2025-11-W1", "to_week": "2025-11-W2"}, headers=headers)
    assert cf.status_code == 200, cf.text
    row2b = next(x for x in cf.json()["rows"] if x["bond_id"] == b["id"])
    assert row2b["volume"] == 50


def test_weekly_volume_conflict(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "WK03")
    first = client.put(f"/api/weekly/2025-11-W3/bonds/{b['id']}", json={"volume": 10}, headers=headers)
    assert first.status_code == 200
    stale = client.put(f"/api/weekly/2025-11-W3/bonds/{b['id']}", json={"volume": 20}, headers=headers)
    assert stale.status_code == 409


def test_compliance_checklist_crud_and_count(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "CMP01")
    entries = client.get(f"/api/bonds/{b['id']}/compliance", params={"month": "2025-11"}, headers=headers).json()
    assert len(entries) == 9  # 5 CBTT + 4 kiểm tra định kỳ items seeded

    bctc = next(g for g in entries if g["item_key"] == "bctc_nam")
    created = client.post(
        f"/api/bonds/{b['id']}/compliance/bctc_nam/entries",
        json={"month_key": "2025-11", "text": "Nộp BCTC năm 2025", "deadline": "2025-11-30"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    entry = created.json()
    assert entry["done"] is False

    done = client.patch(
        f"/api/bonds/{b['id']}/compliance/entries/{entry['id']}",
        json={"text": entry["text"], "done": True, "version": entry["version"]},
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["done"] is True

    refreshed = client.get(f"/api/bonds/{b['id']}/compliance", params={"month": "2025-11"}, headers=headers).json()
    bctc2 = next(g for g in refreshed if g["item_key"] == "bctc_nam")
    assert bctc2["done_count"] == 1
    assert bctc2["total_count"] == 1


def test_dashboard_compliance_count_wired(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "CMP02")
    e1 = client.post(f"/api/bonds/{b['id']}/compliance/bbkt/entries", json={"month_key": "2025-11", "text": "BBKT Q4"}, headers=headers).json()
    client.post(f"/api/bonds/{b['id']}/compliance/ubck/entries", json={"month_key": "2025-11", "text": "BC UBCK"}, headers=headers)
    client.patch(f"/api/bonds/{b['id']}/compliance/entries/{e1['id']}", json={"text": e1["text"], "done": True, "version": e1["version"]}, headers=headers)

    dash = client.get("/api/dashboard/2025-11", headers=headers).json()
    assert dash["compliance_total"] == 2
    assert dash["compliance_done"] == 1


def test_compliance_entry_delete(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "CMP03")
    e = client.post(f"/api/bonds/{b['id']}/compliance/dinh_gia/entries", json={"month_key": "2025-11", "text": "Định giá TSBĐ"}, headers=headers).json()
    r = client.delete(f"/api/bonds/{b['id']}/compliance/entries/{e['id']}", headers=headers)
    assert r.status_code == 200
    entries = client.get(f"/api/bonds/{b['id']}/compliance", params={"month": "2025-11"}, headers=headers).json()
    dg = next(g for g in entries if g["item_key"] == "dinh_gia")
    assert dg["total_count"] == 0


def test_weekly_grid_endpoint(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers, "WKGRID")
    client.put(f"/api/weekly/2025-11-W1/bonds/{b['id']}", json={"volume": 20}, headers=headers)
    client.put(f"/api/weekly/2025-11-W3/bonds/{b['id']}", json={"volume": 40}, headers=headers)

    r = client.get("/api/weekly", params={"start": "2025-11-W1", "end": "2025-12-W1"}, headers=headers)
    assert r.status_code == 200, r.text
    grid = r.json()
    assert "2025-11-W1" in grid["weeks"]
    row = next(x for x in grid["bonds"] if x["bond_id"] == b["id"])
    assert row["cells"]["2025-11-W1"]["volume"] == 20
    assert row["cells"]["2025-11-W2"]["volume"] is None
    assert row["cells"]["2025-11-W3"]["volume"] == 40
