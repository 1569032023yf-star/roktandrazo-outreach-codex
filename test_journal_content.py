"""审计子日志修改故障合同 / Audit child-journal mutation fault contracts."""
import tempfile
import unittest
from pathlib import Path
from autonomy.install_journal import InstallJournal
from autonomy.install_contract import exercise_install_contract
from test_install_contract import RecordingAdapter

class JournalContentTests(unittest.TestCase):
    def test_same_length_mutation_irreversibly_stops_writer(self):
        with tempfile.TemporaryDirectory() as d:
            journal=InstallJournal(d,'op','a'*64,'b'*64)
            try:
                original=journal.path.read_bytes()
                journal.path.write_bytes(original.replace(b'ABSENT',b'TAMPER'))
                changed=journal.path.read_bytes()
                with self.assertRaisesRegex(ValueError,'JOURNAL_CONTENT_CHANGED'):
                    journal.intent('STAGE')
                self.assertEqual(journal.path.read_bytes(),changed)
                journal.path.write_bytes(original)
                with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'):
                    journal.intent('STAGE')
                self.assertEqual(journal.path.read_bytes(),original)
            finally:journal.close()

    def test_mutation_after_intent_prevents_effect_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=RecordingAdapter(Path(d)); path=Path(d)/'op.jsonl'; changed=[]
            def condition():
                if path.exists() and b'INTENT' in path.read_bytes():
                    with path.open('ab') as f:f.write(b'INJECTED\n')
                    changed.append(path.read_bytes())
                return True
            with self.assertRaisesRegex(ValueError,'JOURNAL_CONTENT_CHANGED'):
                exercise_install_contract(d,'op','a'*64,'b'*64,adapter,condition)
            self.assertEqual(adapter.calls,[])
            self.assertEqual(path.read_bytes(),changed[-1])
            fresh=RecordingAdapter(Path(d))
            with self.assertRaises(FileExistsError):
                exercise_install_contract(d,'op','a'*64,'b'*64,fresh,lambda:True)
            self.assertEqual(fresh.calls,[])

    def test_mutation_after_effect_prevents_receipt_and_next_effect(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'op.jsonl'
            class Adapter(RecordingAdapter):
                def apply(self,step,binding):
                    super().apply(step,binding)
                    with path.open('ab') as f:f.write(b'INJECTED\n')
            adapter=Adapter(Path(d))
            with self.assertRaisesRegex(ValueError,'JOURNAL_CONTENT_CHANGED'):
                exercise_install_contract(d,'op','a'*64,'b'*64,adapter,lambda:True)
            self.assertEqual(adapter.calls,['STAGE'])
            self.assertNotIn(b'RECEIPT',path.read_bytes())
            self.assertIn(b'INTENT',path.read_bytes())

if __name__=='__main__':unittest.main()

