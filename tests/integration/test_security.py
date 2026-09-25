"""Checks the data-directory ACL logic against real directories."""

import sys

import pytest

from core.platform import powershell
from core.platform.security import check_directory, is_admin, secure_directory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
]


def test_powershell_roundtrip_with_quotes():
    assert powershell.run_json("@{ v = " + powershell.quote("it's") + " } | ConvertTo-Json") == {
        "v": "it's"
    }


def test_powershell_error_is_raised():
    with pytest.raises(powershell.PowerShellError, match="boom"):
        powershell.run("throw 'boom'")


def test_ordinary_user_directory_is_reported_insecure(tmp_path):
    check = check_directory(tmp_path)
    assert not check.secure
    assert check.problems


def test_missing_directory_is_reported_insecure(tmp_path):
    check = check_directory(tmp_path / "nope")
    assert not check.secure and "does not exist" in check.problems[0]


@pytest.mark.skipif(not is_admin(), reason="needs an elevated terminal")
def test_secure_directory_locks_down_even_a_precreated_tree(tmp_path):
    target = tmp_path / "Sage"
    (target / "snapshots").mkdir(parents=True)
    (target / "snapshots" / "planted.json").write_text("{}", encoding="utf-8")

    secure_directory(target)

    assert check_directory(target).secure
    assert check_directory(target / "snapshots").problems == [
        "inherits permissions from its parent"
    ]
