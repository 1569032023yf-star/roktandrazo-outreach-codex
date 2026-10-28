import json
import subprocess
import unittest
from unittest.mock import Mock
from autonomy.windows_observation import collect_observation, ARGV, MAX_OUTPUT_BYTES

class WindowsObservationTests(unittest.TestCase):
    def setUp(self):
        self.data = dict(sid='S-1-5-21-100-200-300-1001',session_id=2,
            boot_utc='2026-10-27T00:00:00Z',observed_utc='2026-10-28T00:00:00Z')
    def run_data(self, data=None, **kwargs):
        runner = Mock(return_value=subprocess.CompletedProcess(ARGV, 0,
            json.dumps(self.data if data is None else data).encode(), b''))
        return collect_observation(enabled=True, runner=runner, platform='win32', directory_resolver=lambda: ARGV[0], **kwargs)
    def test_disabled_and_nonwindows_never_invoke(self):
        runner = Mock()
        self.assertEqual(collect_observation(runner=runner)['reason'], 'DISABLED')
        self.assertEqual(collect_observation(enabled=True,runner=runner,platform='linux')['reason'],'UNSUPPORTED_PLATFORM')
        runner.assert_not_called()
    def test_success_redacted_and_fixed_arguments(self):
        runner = Mock(return_value=subprocess.CompletedProcess(ARGV,0,json.dumps(self.data).encode(),b''))
        result = collect_observation(enabled=True, runner=runner, platform='win32', directory_resolver=lambda: ARGV[0])
        self.assertEqual(result['reason'],'LOCAL_FACTS_OBSERVED')
        self.assertFalse(result['production_ready']); self.assertFalse(result['signed'])
        self.assertNotIn(self.data['sid'],json.dumps(result))
        self.assertEqual(len(result['facts']['principal_opaque']),64)
        runner.assert_called_once_with(ARGV,shell=False,capture_output=True,timeout=10,check=False,creationflags=0x08000000)
    def test_timeout_and_process_error_redacted(self):
        for error in (subprocess.TimeoutExpired('secret',10),OSError('secret')):
            result=collect_observation(enabled=True,runner=Mock(side_effect=error),platform='win32', directory_resolver=lambda: ARGV[0])
            self.assertIsNone(result['facts']); self.assertNotIn('secret',json.dumps(result))
    def test_output_failure_and_limits(self):
        for code,out,err in ((1,b'',b'secret'),(0,b'{}',b'secret'),(0,b'x'*(MAX_OUTPUT_BYTES+1),b''),(0,'{}',b'')):
            r=Mock(return_value=subprocess.CompletedProcess(ARGV,code,out,err))
            self.assertIsNone(collect_observation(enabled=True,runner=r,platform='win32', directory_resolver=lambda: ARGV[0])['facts'])
    def test_schema_types_and_dates(self):
        for field,value in (('session_id',True),('session_id',-1),('sid','secret'),('boot_utc','2027-01-01T00:00:00Z'),('observed_utc','2026-02-30T00:00:00Z'),('observed_utc','today')):
            data=dict(self.data);data[field]=value
            self.assertEqual(self.run_data(data)['reason'],'INVALID_OBSERVATION')
        data=dict(self.data,extra='secret')
        self.assertEqual(self.run_data(data)['reason'],'INVALID_OBSERVATION')
    def test_duplicate_and_invalid_json(self):
        for raw in (b'{"sid":1,"sid":2}',b'\xff',b'[]',b'{'):
            r=Mock(return_value=subprocess.CompletedProcess(ARGV,0,raw,b''))
            self.assertEqual(collect_observation(enabled=True,runner=r,platform='win32', directory_resolver=lambda: ARGV[0])['reason'],'INVALID_OBSERVATION')

    def test_unicode_sid_digits_fail_closed(self):
        data=dict(self.data,sid='S-1-\u0665-\u0662\u0661')
        result=self.run_data(data)
        self.assertEqual(result['reason'],'INVALID_OBSERVATION')
        self.assertIsNone(result['facts'])

if __name__ == '__main__': unittest.main()
