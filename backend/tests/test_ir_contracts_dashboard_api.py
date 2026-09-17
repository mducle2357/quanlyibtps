from tests.conftest import auth_headers


def test_ir_job_crud_and_monthly_revenue(client, staff_user):
    headers = auth_headers(staff_user)
    job = client.post("/api/ir-jobs", json={"name": "Tư vấn niêm yết"}, headers=headers).json()
    r = client.put(f"/api/ir-jobs/{job['id']}/monthly/2025-11", json={"revenue": 50}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["monthly_values"]["2025-11"]["revenue"] == 50

    renamed = client.patch(f"/api/ir-jobs/{job['id']}", json={"name": "Tư vấn niêm yết (mới)", "version": job["version"]}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Tư vấn niêm yết (mới)"


def test_contracts_project_and_contract_crud(client, staff_user):
    headers = auth_headers(staff_user)
    project = client.post("/api/contracts/projects", json={"name": "Dự án ABC"}, headers=headers).json()
    assert project["roman_index"] == project["roman_index"]  # server-computed, just sanity

    c = client.post(
        f"/api/contracts/projects/{project['id']}/contracts",
        json={"contract_date": "2025-11-01", "title": "HĐ tư vấn phát hành", "status": "Ongoing"},
        headers=headers,
    )
    assert c.status_code == 201, c.text
    contract = c.json()

    upd = client.patch(
        f"/api/contracts/projects/{project['id']}/contracts/{contract['id']}",
        json={"contract_date": "2025-11-01", "title": "HĐ tư vấn phát hành (updated)", "status": "Done", "version": contract["version"]},
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["status"] == "Done"


def test_contract_invalid_status_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    project = client.post("/api/contracts/projects", json={"name": "Dự án X"}, headers=headers).json()
    r = client.post(f"/api/contracts/projects/{project['id']}/contracts", json={"title": "abc", "status": "NotAStatus"}, headers=headers)
    assert r.status_code == 422


def test_dashboard_revenue_breakdown_test10(client, staff_user):
    headers = auth_headers(staff_user)
    bond_a = client.post("/api/bonds", json={"code": "DASHA"}, headers=headers).json()
    client.patch(
        f"/api/bonds/{bond_a['id']}",
        json={"code": "DASHA", "issue_date": "2025-09-01", "maturity_date": "2030-09-01", "first_fee_date": "2025-09-01", "pay_freq_months": 3, "par_value": 100, "version": bond_a["version"]},
        headers=headers,
    )
    ic_a = client.get(f"/api/bonds/{bond_a['id']}", headers=headers).json()["interest_config"]
    client.patch(f"/api/bonds/{bond_a['id']}/interest-config", json={"rate_type": "fixed", "fixed_rate": 10, "version": ic_a["version"]}, headers=headers)
    fee_a = next(f for f in client.get(f"/api/bonds/{bond_a['id']}", headers=headers).json()["fee_configs"] if f["fee_type_key"] == "advisory")
    client.patch(
        f"/api/bonds/{bond_a['id']}/fees/advisory",
        json={"default_rate": 1, "method": "once", "recognition_month": "2025-11", "freq_months": 1, "timing": "end", "version": fee_a["version"]},
        headers=headers,
    )
    client.put(f"/api/bonds/{bond_a['id']}/monthly/2025-11", json={"advised_volume": 100}, headers=headers)

    ir_job = client.post("/api/ir-jobs", json={"name": "IR Job"}, headers=headers).json()
    client.put(f"/api/ir-jobs/{ir_job['id']}/monthly/2025-11", json={"revenue": 50}, headers=headers)

    dash = client.get("/api/dashboard/2025-11", headers=headers).json()
    assert dash["fee_total"] == 100 * 100 * 0.01  # par * advised * 1%
    assert dash["ir_revenue"] == 50
    assert abs(dash["total_revenue"] - (dash["fee_total"] + dash["coupon_revenue"] + 50)) < 1e-9


def test_dashboard_portfolio_limit_test8_test16(client, staff_user):
    headers = auth_headers(staff_user)

    def make_bond(code, par, holding):
        b = client.post("/api/bonds", json={"code": code}, headers=headers).json()
        b = client.patch(
            f"/api/bonds/{b['id']}",
            json={"code": code, "issue_date": "2025-09-01", "maturity_date": "2030-09-01", "pay_freq_months": 3, "par_value": par, "version": b["version"]},
            headers=headers,
        ).json()
        client.put(f"/api/bonds/{b['id']}/monthly/2025-11", json={"invested_volume": holding, "sold_volume": 0}, headers=headers)
        return b

    make_bond("LIMA", 100, 10)
    make_bond("LIMB", 1, 100)

    client.put("/api/dashboard/equity/2025-11", json={"value": 10000}, headers=headers)
    dash = client.get("/api/dashboard/2025-11", headers=headers).json()
    assert dash["limit"] == 7000
    assert dash["holding_value"] == 1100  # 100*10 + 1*100, not 10+100


def test_dashboard_alerts_maturity_and_benchmark(client, staff_user):
    from datetime import date, timedelta

    headers = auth_headers(staff_user)
    soon = (date.today() + timedelta(days=10)).isoformat()
    b = client.post("/api/bonds", json={"code": "MATSOON"}, headers=headers).json()
    client.patch(
        f"/api/bonds/{b['id']}",
        json={"code": "MATSOON", "issue_date": "2020-01-01", "maturity_date": soon, "pay_freq_months": 3, "par_value": 100, "version": b["version"]},
        headers=headers,
    )
    r = client.get("/api/dashboard/alerts/upcoming", headers=headers)
    assert r.status_code == 200
    assert any(a["category"] == "maturity" and "MATSOON" in a["title"] for a in r.json())
