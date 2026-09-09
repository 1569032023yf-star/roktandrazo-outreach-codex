import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.schema_fixture import (
    SCHEMA_CONTRACT_VERSION,
    assert_schema_contract,
    create_test_database,
)


class SchemaContractTests(unittest.TestCase):
    def test_canonical_builder_covers_phase2_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = create_test_database(Path(directory) / "fixture.sqlite")
            try:
                assert_schema_contract(conn)
            finally:
                conn.close()

    def test_stale_version_fails_clearly(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE test_schema_contract(singleton INTEGER PRIMARY KEY, version INTEGER)")
            conn.execute("INSERT INTO test_schema_contract VALUES(1,?)", (SCHEMA_CONTRACT_VERSION - 1,))
            with self.assertRaisesRegex(AssertionError, "STALE_TEST_DB_SCHEMA"):
                assert_schema_contract(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
