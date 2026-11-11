import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.auth.telegram import InitDataError, sign, validate_init_data
from app.config import Settings, get_settings
from app.main import app

TOKEN = "123456:TEST-TOKEN"
MAX_AGE = 3600


def make_init_data(token: str = TOKEN, auth_date: int | None = None, **extra: str) -> str:
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": 42, "first_name": "Єгор", "username": "jegor"}),
        **extra,
    }
    fields["hash"] = sign(fields, token)
    return urlencode(fields)


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


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(
        bot_token=TOKEN, init_data_max_age=MAX_AGE, dev_auth=False
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_me_with_valid_init_data(client):
    resp = client.get("/api/me", headers={"Authorization": f"tma {make_init_data()}"})
    assert resp.status_code == 200
    assert resp.json()["telegram_id"] == 42


def test_dev_auth_disabled_by_default(client):
    assert client.get("/api/me", headers={"Authorization": "dev x"}).status_code == 401
