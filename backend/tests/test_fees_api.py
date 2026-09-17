from tests.conftest import auth_headers


def setup_bond(client, headers, code="FEE01"):
    bond = client.post("/api/bonds", json={"code": code}, headers=headers).json()
    b = client.patch(
        f"/api/bonds/{bond['id']}",
        json={
            "code": code, "issue_date": "2025-10-01", "maturity_date": "2030-10-01",
            "first_fee_date": "2025-10-01", "pay_freq_months": 3, "par_value": 100, "version": bond["version"],
        },
        headers=headers,
    ).json()
    return b


def get_fee_cfg(client, headers, bond_id, key):
    detail = client.get(f"/api/bonds/{bond_id}", headers=headers).json()
    return next(f for f in detail["fee_configs"] if f["fee_type_key"] == key)


def test_default_fee_configs_created_with_bond(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    detail = client.get(f"/api/bonds/{b['id']}", headers=headers).json()
    keys = {f["fee_type_key"] for f in detail["fee_configs"]}
    assert keys == {"advisory", "issuing", "custody", "nshtp", "collateral", "other"}


def test_once_fee_advisory_test(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    cfg = get_fee_cfg(client, headers, b["id"], "advisory")
    r = client.patch(
        f"/api/bonds/{b['id']}/fees/advisory",
        json={"default_rate": 0.5, "method": "once", "recognition_month": "2025-11", "freq_months": 1, "timing": "end", "version": cfg["version"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    client.put(f"/api/bonds/{b['id']}/monthly/2025-11", json={"advised_volume": 2000}, headers=headers)

    computed = client.get(f"/api/bonds/{b['id']}/computed", params={"start": "2025-10", "end": "2025-12"}, headers=headers).json()
    by_month = {c["month_key"]: c for c in computed}
    assert by_month["2025-10"]["fees"]["advisory"] == 0
    assert by_month["2025-11"]["fees"]["advisory"] == 100 * 2000 * 0.005
    assert by_month["2025-12"]["fees"]["advisory"] == 0


def test_fee_rate_schedule_proration_test15(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    cfg = get_fee_cfg(client, headers, b["id"], "custody")
    client.patch(
        f"/api/bonds/{b['id']}/fees/custody",
        json={"default_rate": 0.10, "method": "actual", "freq_months": 1, "timing": "end", "version": cfg["version"]},
        headers=headers,
    )
    client.put(f"/api/bonds/{b['id']}/monthly/2026-06", json={"advised_volume": 1000, "buyback_volume": 0}, headers=headers)

    add = client.post(
        f"/api/bonds/{b['id']}/fees/custody/periods",
        json={"effective_from": "2026-06-15", "fee_rate": 0.15},
        headers=headers,
    )
    assert add.status_code == 201, add.text

    computed = client.get(f"/api/bonds/{b['id']}/computed", params={"start": "2026-06", "end": "2026-06"}, headers=headers).json()
    fee_june = computed[0]["fees"]["custody"]
    # Rule adopted (documented in README): rate in effect at period-end date wins for
    # a non-Actual-timed monthly recognition window -> whole June uses 0.15%.
    expected = 100 * 1000 * 0.0015 * 30 / 365
    assert abs(fee_june - expected) < 1e-9


def test_overlapping_fee_period_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    client.post(f"/api/bonds/{b['id']}/fees/custody/periods", json={"effective_from": "2026-01-01", "effective_to": "2026-06-30", "fee_rate": 0.1}, headers=headers)
    r = client.post(f"/api/bonds/{b['id']}/fees/custody/periods", json={"effective_from": "2026-04-01", "fee_rate": 0.2}, headers=headers)
    assert r.status_code == 422
    assert "chồng lấn" in r.json()["message"]


def test_invalid_method_for_once_only_fee_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    cfg = get_fee_cfg(client, headers, b["id"], "advisory")
    r = client.patch(
        f"/api/bonds/{b['id']}/fees/advisory",
        json={"default_rate": 0.5, "method": "actual", "freq_months": 1, "timing": "end", "version": cfg["version"]},
        headers=headers,
    )
    assert r.status_code == 422


def test_delete_fee_period(client, staff_user):
    headers = auth_headers(staff_user)
    b = setup_bond(client, headers)
    added = client.post(f"/api/bonds/{b['id']}/fees/custody/periods", json={"effective_from": "2026-01-01", "fee_rate": 0.2}, headers=headers).json()
    period_id = added["periods"][0]["id"]
    r = client.delete(f"/api/bonds/{b['id']}/fees/custody/periods/{period_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["periods"] == []
