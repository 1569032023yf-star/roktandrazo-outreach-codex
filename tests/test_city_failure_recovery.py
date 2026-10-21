"""SQLite failure and interruption semantics / SQLite提交失败与中断恢复语义。"""
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

from tests.test_city_network_recovery import CityNetworkRecoveryTests
from tests.test_discovery_service import DiscoveryDb
from discovery.discovery_service import DiscoveryService
from discovery.providers.mock_provider import MockPlacesProvider


class CityFailureRecoveryTests(CityNetworkRecoveryTests):
    # The runner selects the two methods defined here, not inherited repetitions.
    def test_failed_commit_can_rollback_the_entire_attempt(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            conn.commit()
            before = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('CREATE TABLE city_commit_parent(id INTEGER PRIMARY KEY)')
            conn.execute('CREATE TABLE city_commit_child(parent_id INTEGER REFERENCES city_commit_parent(id) DEFERRABLE INITIALLY DEFERRED)')
            conn.commit()
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            service.run_website_resolution(city, resolver)
            conn.execute('INSERT INTO city_commit_child VALUES (99)')
            with self.assertRaises(sqlite3.IntegrityError):
                conn.commit()
            conn.rollback()
            self.assertEqual(dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone()), before)

    def test_lost_connection_discards_uncommitted_attempt_and_restart_recovers(self):
        with DiscoveryDb() as conn:
            _, city, row, _, _ = self.missing_website(conn)
            conn.commit()
            path = conn.execute('PRAGMA database_list').fetchone()[2]
            lost = sqlite3.connect(path)
            lost.row_factory = sqlite3.Row
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            DiscoveryService(lost, provider=MockPlacesProvider()).run_website_resolution(city, resolver)
            lost.close()  # Abandoned transaction; no commit, no normal completion.
            saved = conn.execute('SELECT raw_payload_json FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone()[0]
            self.assertNotIn('website_resolution_retry', json.loads(saved))
            service = DiscoveryService(conn, provider=MockPlacesProvider())
            service.run_website_resolution(city, resolver)
            conn.commit()
            saved = conn.execute('SELECT raw_payload_json FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone()[0]
            self.assertEqual(json.loads(saved)['website_resolution_retry']['attempts'], 1)
