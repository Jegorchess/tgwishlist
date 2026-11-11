import time

import pytest

from app.auth.telegram import InitDataError, validate_init_data
from tests.helpers import MAX_AGE, TOKEN, make_init_data


def test_valid_init_data():
    data = validate_init_data(make_init_data(start_param="join_abc"), TOKEN, MAX_AGE)
    assert data.user.id == 42
    assert data.user.first_name == "Єгор"
    assert data.start_param == "join_abc"


def test_forged_signature_rejected():
    raw = make_init_data(token="999:OTHER")
    with pytest.raises(InitDataError, match="signature"):
        validate_init_data(raw, TOKEN, MAX_AGE)


def test_tampered_payload_rejected():
    raw = make_init_data().replace("42", "43")
    with pytest.raises(InitDataError, match="signature"):
        validate_init_data(raw, TOKEN, MAX_AGE)


def test_expired_rejected():
    raw = make_init_data(auth_date=int(time.time()) - MAX_AGE - 10)
    with pytest.raises(InitDataError, match="expired"):
        validate_init_data(raw, TOKEN, MAX_AGE)


def test_missing_hash_rejected():
    with pytest.raises(InitDataError, match="hash"):
        validate_init_data("auth_date=1&user=%7B%7D", TOKEN, MAX_AGE)


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_dev_auth_disabled_by_default(client):
    assert (await client.get("/api/me", headers={"Authorization": "dev x"})).status_code == 401
