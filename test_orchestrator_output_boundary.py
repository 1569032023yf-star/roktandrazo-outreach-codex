import ast
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class OutputBoundaryTests(unittest.TestCase):
    def load_entry(self, root):
        source = Path(__file__).with_name('bd_orchestrator.py').read_text(encoding='utf-8')
        entry = root / 'bd_orchestrator.py'
        entry.write_text(source, encoding='utf-8')
        modules = {'env_loader': types.ModuleType('env_loader')}
        # Isolate external DB/config dependencies; execute the real entry module.
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module in ('bd_db', 'outreach_control'):
                module = modules.setdefault(node.module, types.ModuleType(node.module))
                for name in node.names:
                    setattr(module, name.name, lambda *a, **k: None)
        with patch.dict(sys.modules, modules):
            return runpy.run_path(str(entry))

    def test_import_does_not_create_output_and_explicit_path_is_lazy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = self.load_entry(root)
            self.assertFalse((root / 'output').exists())
            output = root / 'state' / 'reports'
            entry['configure_output_directory'](str(output))
            self.assertEqual(entry['configure_output_directory'].__globals__['OUT_DIR'], output)
            self.assertFalse(output.exists())

    def test_relative_path_rejected_and_default_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = self.load_entry(root)
            configure = entry['configure_output_directory']
            with self.assertRaises(ValueError):
                configure('relative/reports')
            configure(None)
            self.assertEqual(configure.__globals__['OUT_DIR'], root / 'output')


if __name__ == '__main__':
    unittest.main()
