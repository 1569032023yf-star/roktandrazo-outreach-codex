import copy
import hashlib
import hmac
import unittest
from autonomy.bridge_session_evidence import aggregate
from autonomy.host_preparation import EvidenceConsumer, TrustedSource, canonical
from autonomy.unattended_policy import INVENTORY

KEY = b'synthetic-bridge-timeline-fixture-key'


class BridgeSessionTests(unittest.TestCase):
    def setUp(self):
        self.consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'collector', KEY)})
        self.common = dict(schema='rokt.host-evidence.v1', source_id='fixture', principal_id='collector',
            inventory_id=INVENTORY, configuration_id='a'*64, bridge_principal_id='bridge-user')
        self.config = dict(self.common, kind='bridge_configuration', observed_at_epoch=100,
            receipt_id='config', hkcu_run_verified=True, startup_mode='machine_boot', interactive_session_required=False)
        self.a = dict(self.common, kind='bridge_observation', observed_at_epoch=110, receipt_id='a',
            call_id='call-a', boot_id='boot-a', logon_id='service-session', instance_id='instance-a',
            authenticated=True, post_health_ok=True, interactive_login_present=False, method='POST', endpoint='health')
        self.b = dict(self.a, observed_at_epoch=130, receipt_id='b', call_id='call-b')
        self.window = dict(self.common, kind='bridge_os_event_window', observed_at_epoch=140, receipt_id='window',
            boot_id='boot-a', coverage_from=100, coverage_to=130, complete=True, gaps_detected=False,
            all_interactive_sessions_included=True, initial_interactive_sessions=0, first_sequence=1,last_sequence=2,
            events=[dict(sequence=1,type='boot',at_epoch=100),dict(sequence=2,type='coverage_end',at_epoch=130)])

    def signed(self, payload):
        return dict(payload=copy.deepcopy(payload),mac=hmac.new(KEY,canonical(payload),hashlib.sha256).hexdigest())

    def run_case(self):
        return aggregate(self.consumer,self.signed(self.config),[self.signed(self.a),self.signed(self.b)],self.signed(self.window),now=140)

    def relogon(self):
        self.a.update(logon_id='old-logon',interactive_login_present=True)
        self.b.update(logon_id='new-logon',interactive_login_present=True,instance_id='instance-b')
        self.window.update(coverage_from=110,first_sequence=7,last_sequence=9,initial_interactive_sessions=1,
            events=[dict(sequence=7,type='logoff',at_epoch=115,logon_id='old-logon',user_id='user-a'),
                    dict(sequence=8,type='logon',at_epoch=120,logon_id='new-logon',user_id='user-a'),
                    dict(sequence=9,type='coverage_end',at_epoch=130)])

    def test_machine_boot_without_login_and_idempotent_digest(self):
        r=self.run_case()
        self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['CROSS_CALL_VERIFIED'],'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['CROSS_LOGON_VERIFIED'],'NOT_VERIFIED')
        self.assertEqual(self.run_case(),r)

    def test_normal_logout_login_recovery_distinct_from_boot(self):
        self.relogon();r=self.run_case()
        self.assertEqual(r['CROSS_LOGON_VERIFIED'],'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')
        self.assertEqual(r['CROSS_CALL_VERIFIED'],'NOT_VERIFIED')
        self.assertEqual(r['PROCESS_OBSERVATION'],'DIFFERENT_INSTANCE_ENDPOINTS')

    def test_resigned_observations_do_not_make_new_acceptance_cycle(self):
        original=self.run_case()
        for row in (self.config,self.a,self.b,self.window):row['receipt_id']+='-renewed'
        renewed=self.run_case()
        self.assertEqual(original['acceptance_id'],renewed['acceptance_id'])
        self.assertNotEqual(original['evidence_digest'],renewed['evidence_digest'])

    def test_hkcu_run_never_implies_no_login(self):
        self.config['startup_mode']='hkcu_run';r=self.run_case()
        self.assertEqual(r['HKCU_RUN_CONFIGURED'],'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_missing_window_endpoints_do_not_prove_boot(self):
        r=aggregate(self.consumer,self.signed(self.config),[self.signed(self.a),self.signed(self.b)],None,now=140)
        self.assertEqual(r['CROSS_CALL_VERIFIED'],'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_gaps_and_unknown_events_reject_extended_acceptance(self):
        original=copy.deepcopy(self.window)
        for field,value in [('complete',False),('gaps_detected',True),('all_interactive_sessions_included',False),
                            ('coverage_from',111),('coverage_to',129),('last_sequence',4)]:
            self.window=dict(original,**{field:value})
            with self.subTest(field=field):self.assertEqual(self.run_case()['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')
        self.window=original;self.window['events'][0]['type']='unknown'
        self.assertEqual(self.run_case()['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_interactive_login_event_blocks_no_login_even_logged_out(self):
        self.window['events']=[dict(sequence=1,type='boot',at_epoch=100),
            dict(sequence=2,type='logon',at_epoch=115,logon_id='temporary',user_id='other-user'),
            dict(sequence=3,type='logoff',at_epoch=120,logon_id='temporary',user_id='other-user'),
            dict(sequence=4,type='coverage_end',at_epoch=130)]
        self.window['last_sequence']=4
        self.assertEqual(self.run_case()['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_duplicate_receipt_call_and_out_of_order(self):
        original=dict(self.b)
        for fields in ({'receipt_id':'a'},{'call_id':'call-a'},{'observed_at_epoch':110}):
            self.b=dict(original,**fields)
            with self.subTest(fields=fields):
                r=self.run_case();self.assertEqual(r['CROSS_CALL_VERIFIED'],'NOT_VERIFIED');self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_identity_config_and_boot_changes(self):
        original=dict(self.b)
        for fields in ({'bridge_principal_id':'other'},{'configuration_id':'b'*64},{'boot_id':'new-boot'},
                       {'principal_id':'other'},{'method':'GET'}):
            self.b=dict(original,**fields)
            with self.subTest(fields=fields):
                r=self.run_case();self.assertEqual(r['CROSS_CALL_VERIFIED'],'NOT_VERIFIED');self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'],'NOT_VERIFIED')

    def test_relogon_requires_matching_user_order_and_complete_lifecycle(self):
        self.relogon();original=copy.deepcopy(self.window)
        for fields in ({'user_id':'other-user'},{'logon_id':'unrelated'},{'at_epoch':114}):
            self.window=copy.deepcopy(original);self.window['events'][1].update(fields)
            with self.subTest(fields=fields):self.assertEqual(self.run_case()['CROSS_LOGON_VERIFIED'],'NOT_VERIFIED')

    def test_relogon_rejects_new_session_ended_or_old_session_revived(self):
        self.relogon();original=copy.deepcopy(self.window)
        for kind,logon in (('logoff','new-logon'),('logon','old-logon')):
            self.window=copy.deepcopy(original)
            self.window['events'].insert(2,dict(sequence=9,type=kind,at_epoch=125,logon_id=logon,user_id='user-a'))
            self.window['events'][-1]['sequence']=10;self.window['last_sequence']=10
            with self.subTest(kind=kind):self.assertEqual(self.run_case()['CROSS_LOGON_VERIFIED'],'NOT_VERIFIED')

    def test_bad_signature_and_stale_config_are_redacted(self):
        e=self.signed(self.config);e['payload']['configuration_id']='secret'
        r=aggregate(self.consumer,e,[],None,now=140)
        self.assertNotIn('secret',str(r));self.assertEqual(r['HKCU_RUN_CONFIGURED'],'NOT_VERIFIED')
        r=aggregate(self.consumer,self.signed(self.config),[],None,now=401)
        self.assertEqual(r['HKCU_RUN_CONFIGURED'],'NOT_VERIFIED')

    def test_probe_timestamp_logoff_is_ambiguous_and_rejected(self):
        self.relogon()
        self.window['events'].insert(2,dict(sequence=9,type='logoff',at_epoch=130,logon_id='new-logon',user_id='user-a'))
        self.window['events'][-1]['sequence']=10
        self.window['last_sequence']=10
        self.assertEqual(self.run_case()['CROSS_LOGON_VERIFIED'],'NOT_VERIFIED')


if __name__=='__main__':unittest.main()
