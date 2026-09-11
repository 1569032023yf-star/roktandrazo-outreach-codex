"""Discovery and backlog coexistence / 新发现与积压恢复共存回归。"""
import ast
import json
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bd_orchestrator
from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import activate_next_city
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result
from tests.schema_fixture import create_test_database


class DiscoveryCoexistenceTests(unittest.TestCase):
    def canonical(self, conn, safe):
        city = activate_next_city(conn)
        conn.commit()
        database = conn.execute('PRAGMA database_list').fetchone()[2]
        service = Mock()
        calls = []
        for name in ('run_places_batch','run_website_resolution','run_staging_postprocess','run_linked_backlog'):
            value = {} if name=='run_linked_backlog' else SimpleNamespace(results_seen=0,new_unique_places=0)
            def execute(*args, _name=name, _value=value, **kwargs):
                calls.append(_name)
                return _value
            getattr(service,name).side_effect=execute
        with ExitStack() as stack:
            stack.enter_context(patch.object(bd_orchestrator,'get_db',side_effect=lambda:sqlite3.connect(database)))
            for name in ('set_execution_mode','update_job_run','release_run_lock'):
                stack.enter_context(patch.object(bd_orchestrator,name))
            stack.enter_context(patch.object(bd_orchestrator,'acquire_run_lock',return_value=True))
            stack.enter_context(patch.object(bd_orchestrator,'_resolve_active_discovery_state',return_value=('TN',None)))
            stack.enter_context(patch.object(bd_orchestrator,'_count_broad_ready_pool',return_value=34))
            stack.enter_context(patch.object(bd_orchestrator,'_count_safe_ready_pool',return_value=safe))
            constructor=stack.enter_context(patch('discovery.discovery_service.DiscoveryService',return_value=service))
            stack.enter_context(patch('retail_city_queue.activate_next_city',return_value=city))
            stack.enter_context(patch('retail_city_queue.seed_default_queue'))
            finish=stack.enter_context(patch.object(bd_orchestrator,'finish_job_run'))
            outcome=bd_orchestrator.stage_inventory('coexistence','2026-09-11',False)
        return outcome,calls,finish,constructor,service

    def test_zero_discovery_and_backlog_both_execute_in_order(self):
        with DiscoveryDb() as conn:
            outcome,calls,finish,_,service=self.canonical(conn,1)
            self.assertFalse(outcome)
            self.assertEqual(calls,['run_places_batch','run_website_resolution','run_staging_postprocess','run_linked_backlog'])
            self.assertEqual(finish.call_args.args[1],'partial')
            self.assertEqual(finish.call_args.kwargs['stop_reason'],'safe_inventory_gap')
            self.assertEqual(finish.call_args.kwargs['gap'],29)
            self.assertTrue(service.run_website_resolution.call_args.kwargs['unlinked_only'])
            self.assertTrue(service.run_staging_postprocess.call_args.kwargs['unlinked_only'])

    def test_safe_target_met_skips_all_replenishment(self):
        with DiscoveryDb() as conn:
            outcome,calls,finish,constructor,_=self.canonical(conn,30)
            self.assertTrue(outcome)
            self.assertEqual(calls,[])
            constructor.assert_not_called()
            self.assertEqual(finish.call_args.kwargs['stop_reason'],'target_met')

    def test_new_merchant_resolution_and_visible_evidence(self):
        with DiscoveryDb() as conn:
            city=activate_next_city(conn)
            item=result('New Board Game Depot',result_id='new-discovery-coexistence',website='',email='')
            page=ProviderPage('mock','toy store Nashville TN','Nashville','TN','',[item])
            service=DiscoveryService(conn,provider=MockPlacesProvider({('toy store Nashville TN',''):page}))
            self.assertEqual(service.run_places_batch(city).new_unique_places,1)
            resolver=Mock()
            resolver.resolve.return_value=SimpleNamespace(status='resolved',website='https://new-game.test')
            self.assertEqual(service.run_website_resolution(city,resolver,unlinked_only=True).results_seen,1)
            fetcher=MockFetcher({'https://new-game.test':'New Board Game Depot sales@new-game.test'})
            self.assertEqual(service.run_staging_postprocess(city,fetcher=fetcher,unlinked_only=True).leads_created,1)
            lead=dict(conn.execute('SELECT * FROM leads').fetchone())
            self.assertEqual(lead['email'],'sales@new-game.test')
            ev=json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results').fetchone()[0])['official_email_evidence']
            self.assertIn(ev['email'],ev['visible_text_excerpt'])
            self.assertTrue(ev['http_success'] and ev['tls_success'])

    def test_normal_lanes_do_not_bypass_linked_safety(self):
        from tests.test_phase4a1b_linked_backlog import LinkedBacklogTests
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET status='suppressed'")
            conn.execute("UPDATE lead_discovery_results SET validation_status='email_extraction_pending'")
            self.assertEqual(service.run_staging_postprocess(city,fetcher=fetch,unlinked_only=True).results_seen,0)
            self.assertEqual(service.run_linked_backlog(city,Mock(),fetcher=fetch)['processed'],0)
            self.assertFalse(fetch.requested)

    def test_no_legacy_or_send_authority_in_inventory(self):
        source=Path(bd_orchestrator.__file__).read_text(encoding='utf-8')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='stage_inventory')
        body=ast.get_source_segment(source,node)
        for forbidden in ('http_scan_website','inventory_monitor_executor','create_plan','create_authorization','smtplib','imaplib','send_email'):
            self.assertNotIn(forbidden,body)

    def test_protected_tables_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = create_test_database(Path(directory) / 'contract.db')
            tables=['final_send_plan','send_authorizations','send_authorization_entries','send_log']
            before={t:list(conn.execute(f'SELECT * FROM {t}')) for t in tables}
            self.canonical(conn,1)
            self.assertEqual(before,{t:list(conn.execute(f'SELECT * FROM {t}')) for t in tables})
            conn.close()
