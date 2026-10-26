def test_login_success(client, clinic):
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["clinic_id"] == clinic.id
    assert data["role"] == "admin"
    assert data["user_id"] > 0


def test_login_wrong_password(client, clinic):
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "WrongPass!"},
    )
    assert res.status_code == 401


def test_login_unknown_email(client, clinic):
    res = client.post(
        "/auth/login",
        json={"email": "nobody@abc.test", "password": "Secret123!"},
    )
    assert res.status_code == 401


def test_login_is_case_insensitive(client, clinic):
    res = client.post(
        "/auth/login",
        json={"email": "ADMIN@ABC.TEST", "password": "Secret123!"},
    )
    assert res.status_code == 200


def test_token_works_for_clinic_endpoint(client, clinic):
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!"},
    )
    token = res.json()["access_token"]
    res = client.get("/clinics/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["id"] == clinic.id


def test_bad_token_rejected(client, clinic):
    res = client.get("/clinics/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401
def _second_clinic_same_email(db_session):
    """A SECOND clinic whose admin uses the SAME email as the `clinic` fixture.

    Reproduces the cross-tenant login collision: two clinics, identical admin
    email and password. The API must never silently authenticate one of them.
    """
    from app.services.clinic_service import create_clinic

    return create_clinic(
        db_session,
        name="Second Dental Clinic",
        slug="second-clinic",
        admin_email="admin@abc.test",  # same email as the `clinic` fixture
        admin_password="Secret123!",
    )


def test_login_same_email_two_clinics_never_silently_picks_tenant(client, db_session, clinic):
    _second_clinic_same_email(db_session)
    res = client.post(
        "/auth/login", json={"email": "admin@abc.test", "password": "Secret123!"}
    )
    assert res.status_code == 401
    assert "clinic_slug" in res.json()["detail"]


def test_login_with_clinic_slug_matches_first_clinic(client, db_session, clinic):
    _second_clinic_same_email(db_session)
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!", "clinic_slug": clinic.slug},
    )
    assert res.status_code == 200
    assert res.json()["clinic_id"] == clinic.id
    token = res.json()["access_token"]
    me = client.get("/clinics/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == clinic.id


def test_login_with_clinic_slug_matches_second_clinic(client, db_session):
    from app.services.clinic_service import create_clinic

    first = create_clinic(
        db_session, name="First Clinic", slug="first-clinic",
        admin_email="admin@abc.test", admin_password="Secret123!",
    )
    second = create_clinic(
        db_session, name="Second Clinic", slug="second-clinic",
        admin_email="admin@abc.test", admin_password="Secret123!",
    )
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!", "clinic_slug": second.slug},
    )
    assert res.status_code == 200
    assert res.json()["clinic_id"] == second.id
    first_res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!", "clinic_slug": first.slug},
    )
    assert first_res.status_code == 200
    assert first_res.json()["clinic_id"] == first.id


def test_login_with_unknown_clinic_slug_is_rejected(client, db_session, clinic):
    _second_clinic_same_email(db_session)
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "Secret123!", "clinic_slug": "no-such-clinic"},
    )
    assert res.status_code == 401


def test_login_with_slug_validates_that_clinics_password(client, db_session, clinic):
    # The same email exists in two clinics, but with DIFFERENT passwords. A slug
    # scoped login must only accept the password for the requested clinic.
    from app.services.clinic_service import create_clinic

    create_clinic(
        db_session, name="Second Dental Clinic", slug="second-clinic",
        admin_email="admin@abc.test", admin_password="DifferentPass!",
    )
    # Second clinic's password must NOT authenticate against the first clinic.
    res = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "DifferentPass!", "clinic_slug": clinic.slug},
    )
    assert res.status_code == 401
    # ...but it DOES authenticate against the second clinic.
    ok = client.post(
        "/auth/login",
        json={"email": "admin@abc.test", "password": "DifferentPass!", "clinic_slug": "second-clinic"},
    )
    assert ok.status_code == 200
    assert ok.json()["clinic_id"] != clinic.id


def test_login_single_tenant_still_works_without_slug(client, db_session, clinic):
    # Backward compatibility: no second clinic -> bare email+password stays OK.
    res = client.post(
        "/auth/login", json={"email": "admin@abc.test", "password": "Secret123!"}
    )
    assert res.status_code == 200
    assert res.json()["clinic_id"] == clinic.id