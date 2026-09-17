from tests.conftest import auth_headers


def test_create_manual_rate_and_set_monthly_value(client, staff_user):
    headers = auth_headers(staff_user)
    r = client.post("/api/reference-rates", json={"name": "TPB 12M", "rate_type": "manual"}, headers=headers)
    assert r.status_code == 201, r.text
    rate_id = r.json()["id"]

    r = client.put(f"/api/reference-rates/{rate_id}/monthly/2025-11", json={"rate": 5.5}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["monthly_values"]["2025-11"]["rate"] == 5.5

    # Updating again without the correct version must be rejected (optimistic lock).
    stale = client.put(f"/api/reference-rates/{rate_id}/monthly/2025-11", json={"rate": 6.0}, headers=headers)
    assert stale.status_code == 409

    ok_version = r.json()["monthly_values"]["2025-11"]["version"]
    ok = client.put(f"/api/reference-rates/{rate_id}/monthly/2025-11", json={"rate": 6.0, "version": ok_version}, headers=headers)
    assert ok.status_code == 200
    assert ok.json()["monthly_values"]["2025-11"]["rate"] == 6.0


def test_calculated_rate_requires_components(client, staff_user):
    headers = auth_headers(staff_user)
    r = client.post("/api/reference-rates", json={"name": "Avg X", "rate_type": "calculated"}, headers=headers)
    assert r.status_code == 422


def test_circular_dependency_rejected(client, staff_user):
    headers = auth_headers(staff_user)
    a = client.post("/api/reference-rates", json={"name": "A", "rate_type": "manual"}, headers=headers).json()
    b = client.post(
        "/api/reference-rates",
        json={"name": "B", "rate_type": "calculated", "calc_method": "average", "component_ids": [a["id"]]},
        headers=headers,
    ).json()
    # Now try to make A a calculated rate that depends on B -> A -> B cycle.
    # A is currently manual; simulate by trying to update B to include itself indirectly via a new rate C that includes B, then updating A...
    # Simpler direct check: try to update B's components to include B itself.
    r = client.patch(
        f"/api/reference-rates/{b['id']}",
        json={"name": "B", "calc_method": "average", "component_ids": [b["id"]], "version": b["version"]},
        headers=headers,
    )
    assert r.status_code == 422


def test_optimistic_lock_conflict_on_rename(client, staff_user):
    headers = auth_headers(staff_user)
    created = client.post("/api/reference-rates", json={"name": "VNIBOR", "rate_type": "manual"}, headers=headers).json()
    ok = client.patch(
        f"/api/reference-rates/{created['id']}",
        json={"name": "VNIBOR 2", "calc_method": None, "component_ids": [], "version": created["version"]},
        headers=headers,
    )
    assert ok.status_code == 200
    stale = client.patch(
        f"/api/reference-rates/{created['id']}",
        json={"name": "VNIBOR 3", "calc_method": None, "component_ids": [], "version": created["version"]},
        headers=headers,
    )
    assert stale.status_code == 409
    assert "thay đổi bởi người dùng khác" in stale.json()["message"]


def test_viewer_cannot_create_rate(client, db_session):
    from tests.conftest import make_user

    viewer = make_user(db_session, "viewer-test@tps.vn", "Viewer")
    headers = auth_headers(viewer)
    r = client.post("/api/reference-rates", json={"name": "X", "rate_type": "manual"}, headers=headers)
    assert r.status_code == 403


def test_resolved_values_averages_calculated_rate(client, staff_user):
    headers = auth_headers(staff_user)
    a = client.post("/api/reference-rates", json={"name": "RateA", "rate_type": "manual"}, headers=headers).json()
    client.put(f"/api/reference-rates/{a['id']}/monthly/2025-11", json={"rate": 4.0}, headers=headers)
    b = client.post("/api/reference-rates", json={"name": "RateB", "rate_type": "manual"}, headers=headers).json()
    client.put(f"/api/reference-rates/{b['id']}/monthly/2025-11", json={"rate": 6.0}, headers=headers)
    calc = client.post(
        "/api/reference-rates",
        json={"name": "Avg AB", "rate_type": "calculated", "calc_method": "average", "component_ids": [a["id"], b["id"]]},
        headers=headers,
    ).json()

    r = client.get("/api/reference-rates/resolved", params={"start": "2025-11", "end": "2025-11"}, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data[calc["id"]]["2025-11"] == 5.0
