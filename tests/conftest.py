from pathlib import Path
import pytest
from src.storage.database import Database

@pytest.fixture
def db(tmp_path):
    database=Database(str(tmp_path/'test.db')); database.migrate(); return database

@pytest.fixture
def root(): return Path(__file__).parents[1]

