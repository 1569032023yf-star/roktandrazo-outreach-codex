import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from publisher_channel.install_inputs import InstallInputPins


@unittest.skipUnless(os.name == 'nt', 'Windows handles required')
class PinnedStreamingTests(unittest.TestCase):
    def test_streaming_preserves_pin_and_digest_gates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path=Path(directory)/'input.bin'
            data=b'content' * 10000
            path.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
            with InstallInputPins() as pins:
                self.assertEqual(pins.add_verified(path,digest),len(data))
                self.assertEqual(pins.add(path,digest),data)
                with self.assertRaises(OSError):
                    path.write_bytes(b'changed')
                with self.assertRaises(OSError):
                    path.rename(path.with_suffix('.renamed'))
                self.assertTrue(pins.revalidate())
            with InstallInputPins() as pins:
                with self.assertRaisesRegex(ValueError,'DIGEST_MISMATCH'):
                    pins.add_verified(path,'0'*64)
            with InstallInputPins() as pins:
                with self.assertRaisesRegex(ValueError,'LINKS_OR_SIZE'):
                    pins.add_verified(path,digest,limit=1)
