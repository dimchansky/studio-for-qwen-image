import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from io_utils import atomic_json, replace_with_retry


class AtomicUpdateTests(unittest.TestCase):
    def test_reader_temporarily_locks_status(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'status.json'
            target.write_text('{"step":1}', encoding='utf-8')
            original = Path.replace
            attempts = []

            def temporarily_locked(source, destination):
                attempts.append(source)
                if len(attempts) < 3:
                    self.assertEqual(json.loads(target.read_text())['step'], 1)
                    raise PermissionError('A Windows reader still holds the previous file')
                return original(source, destination)

            with patch.object(Path, 'replace', temporarily_locked):
                atomic_json(target, {'step': 2, 'stage': '正在生成'})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['step'], 2)
            self.assertFalse(target.with_suffix('.tmp').exists())

    def test_permanent_denial_is_not_hidden(self):
        with patch.object(Path, 'replace', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):
                replace_with_retry(Path('source'), Path('target'), timeout=0)


if __name__ == '__main__':
    unittest.main()
