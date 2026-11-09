"""The legacy runner must never consume native-controller identities."""
import json
from pathlib import Path
import tempfile
import unittest

from autonomy import supervisor


class LegacyControllerFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.task = dict(id='A-u1-owner-intent-status-review-20261108', workstream='A',
                         role='developer', status='queued', executor='not_started',
                         attempts=0, outcome_unknown=False, blocked_cycles=0)

    def write(self, tasks):
        (self.runtime / 'queue.json').write_text(json.dumps({'tasks': tasks, 'cycles': []}),
                                                 encoding='utf-8')

    def test_registered_identity_cannot_use_legacy_runner_or_recovery(self):
        for task_id in supervisor._CONTROLLER_TASK_IDS:
            with self.subTest(task_id=task_id):
                task = dict(self.task, id=task_id)
                self.write([task])
                self.assertEqual(supervisor.cycle(self.runtime, runner=lambda *_:
                    self.fail('legacy runner must not launch controller task'))['status'], 'idle')
                self.write([dict(task, status='unknown', outcome_unknown=True)])
                before = (self.runtime / 'queue.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'CONTROLLER_RECONCILIATION_REQUIRED'):
                    supervisor.recover_unknown(self.runtime, task_id, lambda _:
                        self.fail('legacy checker must not run'))
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)

    def test_malformed_controller_markers_never_reach_legacy_paths(self):
        markers = [{'controller_claim': value} for value in ({}, None, 'malformed')]
        markers += [{'executor': value} for value in ('controller_claimed', 'controller_running',
                                                       'controller_unknown', 'native_subagent')]
        for marker in markers:
            with self.subTest(marker=marker):
                task = dict(self.task, id='legacy-fixture', **marker)
                self.write([task])
                self.assertEqual(supervisor.cycle(self.runtime, runner=lambda *_:
                    self.fail('legacy runner must not launch marked task'))['status'], 'idle')
                self.write([dict(task, status='unknown', outcome_unknown=True)])
                before = (self.runtime / 'queue.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'CONTROLLER_RECONCILIATION_REQUIRED'):
                    supervisor.recover_unknown(self.runtime, task['id'], lambda _:
                        self.fail('legacy checker must not run'))
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)

    def test_duplicate_ids_never_run_or_recover_either_copy(self):
        task = dict(self.task, id='legacy-fixture')
        marked = dict(task, controller_claim={})
        for items in ([task, marked], [marked, task]):
            with self.subTest(marked_first='controller_claim' in items[0]):
                self.write(items)
                self.assertEqual(supervisor.cycle(self.runtime, runner=lambda *_:
                    self.fail('duplicate task must not run'))['status'], 'idle')
                self.write([dict(t, status='unknown', outcome_unknown=True) for t in items])
                before = (self.runtime / 'queue.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'TASK_ID_NOT_UNIQUE'):
                    supervisor.recover_unknown(self.runtime, task['id'], lambda _:
                        self.fail('legacy checker must not run'))
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
