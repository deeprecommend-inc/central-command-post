"""Tests for AccountDB - SQLite state management"""
import os
import tempfile
import time

import pytest

from src.account_db import AccountDB, AccountStatus


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_accounts.db")
    return AccountDB(db_path)


def test_create_account(db):
    account = db.create_account(area="jp", warmup_days=5)
    assert account.id == 1
    assert account.status == AccountStatus.PENDING
    assert account.area == "jp"
    assert account.warmup_days == 5
    assert account.email == ""
    assert account.sns_accounts == {}


def test_create_batch(db):
    accounts = db.create_batch(count=3, area="us")
    assert len(accounts) == 3
    assert all(a.area == "us" for a in accounts)
    assert [a.id for a in accounts] == [1, 2, 3]


def test_get_account(db):
    created = db.create_account(area="gb")
    fetched = db.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.area == "gb"


def test_get_nonexistent(db):
    assert db.get(999) is None


def test_list_all(db):
    db.create_batch(count=5, area="de")
    all_accounts = db.list_all()
    assert len(all_accounts) == 5


def test_list_by_status(db):
    db.create_batch(count=3, area="us")
    db.update_status(1, AccountStatus.WARMUP)
    db.update_status(2, AccountStatus.WARMUP)

    pending = db.list_by_status(AccountStatus.PENDING)
    warmup = db.list_by_status(AccountStatus.WARMUP)

    assert len(pending) == 1
    assert len(warmup) == 2


def test_next_by_status(db):
    db.create_batch(count=3, area="us")
    db.update_status(1, AccountStatus.WARMUP)

    next_pending = db.next_by_status(AccountStatus.PENDING)
    assert next_pending is not None
    assert next_pending.id == 2  # First pending after #1 was moved to warmup


def test_update_status(db):
    db.create_account(area="us")
    db.update_status(1, AccountStatus.WARMUP)
    account = db.get(1)
    assert account.status == AccountStatus.WARMUP

    db.update_status(1, AccountStatus.FAILED, error="test error")
    account = db.get(1)
    assert account.status == AccountStatus.FAILED
    assert account.error == "test error"


def test_start_warmup(db):
    db.create_account(area="us")
    db.start_warmup(1, profile_id="prof_1", proxy_session="proxy_1")

    account = db.get(1)
    assert account.status == AccountStatus.WARMUP
    assert account.profile_id == "prof_1"
    assert account.proxy_session == "proxy_1"
    assert account.warmup_started is not None


def test_warmup_ready(db):
    db.create_account(area="us", warmup_days=0)  # 0 days = immediately ready
    db.start_warmup(1, profile_id="p", proxy_session="s")

    # warmup_days=0 means immediately ready
    assert db.warmup_ready(1) is True


def test_warmup_not_ready(db):
    db.create_account(area="us", warmup_days=3)
    db.start_warmup(1, profile_id="p", proxy_session="s")

    # Just started, 3 days required
    assert db.warmup_ready(1) is False


def test_set_email(db):
    db.create_account(area="us")
    db.set_email(1, "test@gmail.com")
    assert db.get(1).email == "test@gmail.com"


def test_set_phone(db):
    db.create_account(area="us")
    db.set_phone(1, "+1234567890")
    assert db.get(1).phone_number == "+1234567890"


def test_add_sns_account(db):
    db.create_account(area="us")
    db.add_sns_account(1, "twitter", "testuser")
    db.add_sns_account(1, "instagram", "testuser_ig")

    account = db.get(1)
    assert account.sns_accounts == {
        "twitter": "testuser",
        "instagram": "testuser_ig",
    }


def test_summary(db):
    db.create_batch(count=3, area="us")
    db.update_status(1, AccountStatus.WARMUP)
    db.update_status(2, AccountStatus.ACTIVE)

    summary = db.summary()
    assert summary["pending"] == 1
    assert summary["warmup"] == 1
    assert summary["active"] == 1


def test_delete(db):
    db.create_account(area="us")
    assert db.delete(1) is True
    assert db.get(1) is None
    assert db.delete(999) is False


def test_reset(db):
    db.create_account(area="us")
    db.update_status(1, AccountStatus.FAILED, error="something broke")
    db.start_warmup(1, profile_id="p", proxy_session="s")

    db.reset(1)
    account = db.get(1)
    assert account.status == AccountStatus.PENDING
    assert account.error == ""


def test_status_transitions(db):
    """Test the full status lifecycle"""
    db.create_account(area="us")

    transitions = [
        AccountStatus.WARMUP,
        AccountStatus.CREATING,
        AccountStatus.SMS_WAIT,
        AccountStatus.SNS_EXPAND,
        AccountStatus.ACTIVE,
    ]

    for status in transitions:
        db.update_status(1, status)
        assert db.get(1).status == status


def test_metadata(db):
    db.create_account(area="us", metadata={"key": "value"})
    account = db.get(1)
    assert account.metadata == {"key": "value"}


def test_update_fields(db):
    db.create_account(area="us")
    db.update_fields(1, email="new@gmail.com", area="jp")
    account = db.get(1)
    assert account.email == "new@gmail.com"
    assert account.area == "jp"
