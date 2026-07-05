import sys
from pathlib import Path

# Make the package importable without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

import pytest

from coldemails.models import Person
from coldemails.store import Store

# Tests are offline: never hit Clearbit from company.resolve.
os.environ["COLDEMAILS_NO_NETWORK_RESOLVE"] = "1"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


@pytest.fixture
def person():
    return Person(
        name="Jane Doe",
        email="jane@acme.com",
        title="Recruiter",
        company="Acme",
        domain="acme.com",
    )
