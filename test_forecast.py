import unittest
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError
import server


def cafe_html(*groups):
    return '<h2>Heute</h2><div>Jägerschnitzel</div><h2>Die kommenden Tage</h2>' + ''.join(
        f'<h4>{heading}</h4><div class="ctlg_group_content"><div>{meal}</div></div>'
        for heading, meal in groups)


class ForecastTests(unittest.TestCase):
    def test_cafe_dates_ignore_today_past_scripts_and_footer(self):
        html = cafe_html(('Mittwoch, 07.10.2026', 'Jägerschnitzel'),
                         ('Donnerstag, 08.10.2026', 'Jägerschnitzel'),
                         ('Freitag, 09.10.2026', 'Pasta<script>Jägerschnitzel</script>'),
                         ('Montag, 12.10.2026', 'J&auml;gerschnitzel'))
        html += '<div>Jaegerschnitzel außerhalb der Menügruppe</div><h2>Kontakt</h2>Jägerschnitzel'
        result = server.cafe_future(html, date(2026, 10, 8))
        self.assertEqual(result, {date(2026,10,9): ['Pasta'], date(2026,10,12): ['Jägerschnitzel']})

    def test_cafe_missing_section_is_not_no_match(self):
        with self.assertRaises(ValueError): server.cafe_future('<h2>Heute</h2>Pasta', date(2026,10,8))

    def test_earliest_match_and_tied_sources(self):
        for mensa_day in (date(2026,10,9), date(2026,10,12), date(2026,10,13)):
            with patch.object(server.mensa, 'future', return_value=({mensa_day:['Jaegerschnitzel']}, True)), patch.object(server, 'fetch', return_value=cafe_html(('Montag, 12.10.2026', 'Jägerschnitzel'))):
                result = server.get_forecast(date(2026,10,8))
                self.assertEqual(result['next']['date'], min(mensa_day,date(2026,10,12)).isoformat())
                self.assertEqual(len(result['next']['sources']), 2 if mensa_day.day == 12 else 1)
                self.assertTrue(result['complete'])

    def test_partial_failure_preserves_known_future_match(self):
        with patch.object(server.mensa, 'future', return_value=({date(2026,10,12):['Jägerschnitzel']}, False)), patch.object(server, 'fetch', side_effect=TimeoutError):
            result=server.get_forecast(date(2026,10,8))
            self.assertEqual(result['next']['date'],'2026-10-12')
            self.assertFalse(result['complete'])

    def test_no_announced_match(self):
        with patch.object(server.mensa, 'future', return_value=({},True)), patch.object(server, 'fetch', return_value=cafe_html(('Freitag, 09.10.2026','Pasta'))):
            result=server.get_forecast(date(2026,10,8))
            self.assertIsNone(result['next'])
            self.assertTrue(result['complete'])

    def test_future_mensa_weeks_cross_iso_year_and_skip_today(self):
        client=server.MensaClient()
        def week(day):
            if day.year==2026:
                return {'WeeksToPreview':1,'Days':[{'Date':'2026-12-31T00:00:00Z','Name':'Jägerschnitzel'}]}
            return {'Days':[{'Date':'2027-01-04T00:00:00Z','Name':'Jaegerschnitzel'}]}
        with patch.object(client,'week',side_effect=week) as reader:
            days,complete=client.future(date(2026,12,31))
            self.assertEqual(days,{date(2027,1,4):['Jaegerschnitzel']})
            self.assertEqual(reader.call_count,2)
            self.assertTrue(complete)

    def test_unpublished_weeks_are_not_errors_but_timeouts_are(self):
        for failure,expected in ((None,True),(TimeoutError(),False)):
            client=server.MensaClient()
            with patch.object(client,'week',side_effect=[{'WeeksToPreview':1,'Days':[]},failure]):
                days,complete=client.future(date(2026,10,8))
                self.assertEqual(days,{})
                self.assertEqual(complete,expected)

    def test_week_404_means_unpublished(self):
        client=server.MensaClient();client.token='test';client.environment='Release'
        with patch.object(client,'authenticate'), patch.object(server,'fetch',side_effect=HTTPError('url',404,'missing',{},None)):
            self.assertIsNone(client.week(date(2026,10,8)))


if __name__ == '__main__': unittest.main()
