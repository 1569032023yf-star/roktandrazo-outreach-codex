"""离线日志状态绑定与有界解析 / Offline journal status binding and bounded parsing."""
import json
from pathlib import Path
import tempfile
import unittest
from autonomy.install_journal import InstallJournal,STEPS,inspect_install,MAX_JOURNAL_BYTES

class InspectBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'op.jsonl'
        j=InstallJournal(self.tmp.name,'op','a'*64,'b'*64)
        for step in STEPS:j.intent(step);j.receipt(step,'c'*64)
        j.close();self.raw=self.path.read_bytes()
        self.binding=dict(operation_id='op',manifest_sha256='a'*64,lease_binding='b'*64)

    def test_exact_expected_binding_and_each_mismatch(self):
        result=inspect_install(self.path,expected_binding=self.binding)
        self.assertEqual(result['observed'],'ALL_RECEIPTS_RECORDED');self.assertTrue(result['binding_verified'])
        for key in self.binding:
            altered=dict(self.binding);altered[key]='different'
            result=inspect_install(self.path,expected_binding=altered)
            self.assertEqual(result['observed'],'UNKNOWN');self.assertFalse(result['binding_verified'])
            self.assertFalse(result['allow_install']);self.assertFalse(result['allow_replay'])
        self.assertFalse(inspect_install(self.path)['binding_verified'])
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_invalid_header_binding_never_counts_receipts(self):
        for key,value in [('operation_id',None),('operation_id','../x'),('manifest_sha256','z'*64),('lease_binding',True)]:
            rows=self.raw.splitlines();header=json.loads(rows[0]);header[key]=value
            self.path.write_bytes(json.dumps(header).encode()+b'\n'+b'\n'.join(rows[1:])+b'\n')
            result=inspect_install(self.path)
            self.assertEqual(result['observed'],'UNKNOWN');self.assertEqual(result['completed_steps'],0)

    def test_nonobject_rows_duplicate_keys_and_deep_json_are_unknown(self):
        samples=[b'42\n',b'null\n',b'[]\n',self.raw.replace(b'"kind":"PREPARED"',b'"kind":"wrong","kind":"PREPARED"'),b'['*1100+b'0'+b']'*1100+b'\n',self.raw+b'false\n']
        for sample in samples:
            self.path.write_bytes(sample);result=inspect_install(self.path)
            self.assertEqual(result['observed'],'UNKNOWN');self.assertFalse(result['allow_replay'])
            self.assertEqual(self.path.read_bytes(),sample)

    def test_oversized_log_is_bounded_and_has_no_partial_digest(self):
        sample=self.raw+b' '*MAX_JOURNAL_BYTES+b'\n';self.path.write_bytes(sample)
        result=inspect_install(self.path)
        self.assertTrue(result['oversized']);self.assertIsNone(result['journal_sha256'])
        self.assertEqual(result['observed'],'UNKNOWN');self.assertFalse(result['allow_install'])
        self.assertEqual(self.path.read_bytes(),sample)

if __name__=='__main__':unittest.main()
