import unittest
from datetime import date
from unittest.mock import patch
import server


class MenuTests(unittest.TestCase):
    def setUp(self):
        # Bestehende Heute-Tests benötigen keine echte Vorschau-Netzwerkanfrage.
        patcher = patch.object(server, 'get_forecast', return_value={'next': None, 'complete': True, 'sources': []})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_spellings_and_case(self):
        for text in ('Jägerschnitzel', 'JAEGERSCHNITZEL mit Nudeln', 'Ja\u0308gerschnitzel'):
            self.assertTrue(server.contains_schnitzel(text))
        self.assertFalse(server.contains_schnitzel('Schnitzel mit Jägersauce'))

    def test_cafe_only_today(self):
        html = '<p>Jägerschnitzel</p><h2>Heute</h2><div>Pasta</div><h2>Die kommenden Tage</h2><p>Jaegerschnitzel</p>'
        self.assertEqual(server.cafe_today(html), ['Pasta'])

    def test_cafe_entities_and_nested_heading(self):
        self.assertEqual(server.cafe_today('<h2><span>Heute</span></h2><p>J&auml;gerschnitzel</p><h2>Morgen</h2>'), ['Jägerschnitzel'])

    def test_cafe_ignores_scripts_comments(self):
        lines = server.cafe_today('<h2>Heute</h2><script>"Jägerschnitzel"</script><!-- Jaegerschnitzel --><div>Suppe</div><h2>Morgen</h2>')
        self.assertEqual(lines, ['Suppe'])

    def test_missing_or_unbounded_today_is_error(self):
        for html in ('<h2>Morgen</h2>Jägerschnitzel', '<h2>Heute</h2>Jägerschnitzel'):
            with self.assertRaises(ValueError): server.cafe_today(html)

    def test_mensa_current_date_and_hidden_categories(self):
        menu = {'Days': [
            {'Date': '2026-10-08T00:00:00Z', 'Categories': [
                {'Name': 'Mittag', 'Products': [{'Name': 'Pasta'}]},
                {'IsHidden': True, 'Products': [{'Name': 'Jägerschnitzel'}]}]},
            {'Date': '2026-10-09T00:00:00Z', 'Categories': [{'Products': [{'Name': 'Jaegerschnitzel'}]}]}]}
        self.assertFalse(any(map(server.contains_schnitzel, server.menu_today(menu, date(2026,10,8)))))
        self.assertTrue(any(map(server.contains_schnitzel, server.menu_today(menu, date(2026,10,9)))))
        self.assertEqual(server.menu_today(menu, date(2026,10,10)), [])

    def test_mensa_components_count(self):
        menu = {'Days': [{'Date': '2026-10-08T00:00:00Z', 'Categories': [{'Products': [
            {'Name': 'Menü 1', 'ComponentGroups': [{'Components': [{'Name': 'Jägerschnitzel'}]}]}]}]}]}
        self.assertTrue(any(map(server.contains_schnitzel, server.menu_today(menu, date(2026,10,8)))))

    def test_firestore_decode(self):
        self.assertEqual(server.decode_value({'mapValue': {'fields': {'Days': {'arrayValue': {'values': [{'stringValue': 'today'}]}}}}}), {'Days':['today']})

    def test_either_source_suffices_even_if_other_fails(self):
        for first, second in ((['Jägerschnitzel'], []), ([], ['Jaegerschnitzel']), ([], []), (['Pasta'], ['Suppe'])):
            with patch.object(server.mensa, 'today', return_value=first), patch.object(server, 'fetch', return_value='html'), patch.object(server, 'cafe_today', return_value=second):
                server._cache = None
                result = server.get_status()
                self.assertEqual(result['found'], any(server.contains_schnitzel(t) for t in first+second))
                self.assertEqual(result['message'], server.YES if result['found'] else server.NO)
        with patch.object(server.mensa, 'today', side_effect=TimeoutError), patch.object(server, 'fetch', return_value='html'), patch.object(server, 'cafe_today', return_value=['Jägerschnitzel']):
            server._cache = None
            result = server.get_status()
            self.assertTrue(result['found'])
            self.assertFalse(result['complete'])

    def test_total_failure_defaults_to_no(self):
        with patch.object(server.mensa, 'today', side_effect=TimeoutError), patch.object(server, 'fetch', side_effect=TimeoutError):
            server._cache = None
            result = server.get_status()
            self.assertFalse(result['found'])
            self.assertFalse(result['complete'])
            self.assertEqual(result['message'], server.NO)

    def tearDown(self):
        server._cache = None


if __name__ == '__main__': unittest.main()
