import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_site
import server


class BuildTests(unittest.TestCase):
    def test_only_public_files_are_published(self):
        status = {'date': '2026-10-08', 'checkedAt': '2026-10-08T12:00:00+02:00',
                  'found': False, 'message': server.NO, 'complete': True, 'sources': []}
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'get_status', return_value=status):
            result = build_site.build(temp)
            self.assertEqual({p.name for p in Path(temp).iterdir()}, {'index.html', 'app.js', 'status.json', '.nojekyll'})
            self.assertEqual(json.loads((Path(temp)/'status.json').read_text()), result)
            self.assertEqual(result['updateIntervalMinutes'], 30)
            self.assertNotIn('updateIntervalMinutes', status)

    def test_source_failure_publishes_current_error_not_old_success(self):
        status = {'date': '2026-10-08', 'checkedAt': '2026-10-08T12:00:00+02:00',
                  'found': False, 'message': server.NO, 'complete': False, 'sources': []}
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'get_status', return_value=status):
            (Path(temp)/'status.json').write_text('{"found":true}')
            build_site.build(temp)
            self.assertFalse(json.loads((Path(temp)/'status.json').read_text())['found'])


if __name__ == '__main__': unittest.main()
