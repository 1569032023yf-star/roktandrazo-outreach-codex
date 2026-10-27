from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from autonomy.growth_ledger import GrowthLedger, GrowthError
from test_growth_ledger import consumer, signed, oid, T


class HistoryContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'isolated.sqlite'
        self.ledger=GrowthLedger(self.path,consumer=consumer()); self.ledger.initialize()

    def envelope(self,event='history',**changes):
        data=dict(as_of=T-1,rule=oid('rule'),event_id=oid(event),
                  all_history_complete=True,organizations=[],sites=[],emails=[])
        data.update(changes)
        return signed('growth_history',T,**data)

    def test_empty_history_is_initialized_and_retry_is_idempotent(self):
        original=self.envelope()
        self.assertEqual(self.ledger.import_history(original,now=T),'IMPORTED')
        self.assertEqual(self.ledger.import_history(original,now=T),'DUPLICATE')
        with self.assertRaisesRegex(GrowthError,'^HISTORY_ALREADY_INITIALIZED$'):
            self.ledger.import_history(self.envelope('other'),now=T)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM growth_receipts').fetchone()[0],1)

    def test_malformed_and_duplicate_inputs_leave_no_receipt(self):
        row=dict(id=oid('org'),qualified=True)
        for changes,reason in [({'organizations':{}},'INVALID_HISTORY_SHAPE'),
                ({'organizations':[None]},'INVALID_HISTORY_SHAPE'),
                ({'sites':oid('site')},'INVALID_HISTORY_SHAPE'),
                ({'organizations':[row,row]},'DUPLICATE_HISTORY_ID'),
                ({'emails':[oid('email')]*2},'DUPLICATE_HISTORY_ID')]:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(GrowthError,'^'+reason+'$'):
                    self.ledger.import_history(self.envelope(**changes),now=T)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            for table in ('organizations','assets','growth_receipts','growth_meta'):
                self.assertEqual(conn.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_existing_asset_history_cannot_be_reinitialized(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('INSERT INTO assets VALUES(?,?,?,?)',('site',oid('prior'),T-2,1))
        with self.assertRaisesRegex(GrowthError,'^HISTORY_ALREADY_INITIALIZED$'):
            self.ledger.import_history(self.envelope(),now=T)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM assets').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT count(*) FROM growth_receipts').fetchone()[0],0)


if __name__=='__main__':unittest.main()
