import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Conference, ConferenceEdition, ConferenceSeries
from grouper import build_conferences_from_raw, group_conferences, sort_series, _is_child


def _raw(conf_id, conf_name):
    return {'conf_id': str(conf_id), 'conf_name': conf_name}

def _ed(conf_id, conf_name, year=None, location=None):
    return ConferenceEdition(conf_id=conf_id, conf_name=conf_name,
                             year=year, location=location)


class TestBuildFromRaw(unittest.TestCase):
    def test_basic(self):
        r = build_conferences_from_raw([_raw(9, "УБС-2023")])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].conf_id, 9)

    def test_year_extracted(self):
        r = build_conferences_from_raw([_raw(1, "DCCN 2022, Moscow")])
        self.assertEqual(r[0].year, 2022)

    def test_year_not_in_base(self):
        r = build_conferences_from_raw([_raw(1, "DCCN 2022, Moscow")])
        self.assertNotIn("2022", r[0].base_name)

    def test_series_key_extracted(self):
        r = build_conferences_from_raw([_raw(1, 'Конференция (УБС, Москва)')])
        self.assertEqual(r[0].series_key, 'УБС')

    def test_empty(self):
        self.assertEqual(build_conferences_from_raw([]), [])

    def test_accepts_isand_format(self):
        r = build_conferences_from_raw([{'conf_isand_id': 2037, 'conf_name': 'MLSD 2022'}])
        self.assertEqual(r[0].conf_id, 2037)

    def test_two_editions_same_key(self):
        raw = [_raw(1, "УБС-2023"), _raw(2, "УБС-2024")]
        r = build_conferences_from_raw(raw)
        self.assertEqual(r[0].series_key, r[1].series_key)


class TestIsChild(unittest.TestCase):
    def test_vramkakh_is_child(self):
        self.assertTrue(_is_child(
            'Конференция (УРСС), проводимая в рамках МКПУ', 'abbr'))

    def test_colon_structure_is_child(self):
        self.assertTrue(_is_child(
            'Мультиконференция (МКПУ): конференция УАКС', 'abbr'))

    def test_standalone_not_child(self):
        self.assertFalse(_is_child(
            'Всероссийская мультиконференция (МКПУ, Волгоград)', 'abbr'))

    def test_simple_conf_not_child(self):
        self.assertFalse(_is_child('УБС-2023', 'abbr'))


class TestGroupConferencesF03(unittest.TestCase):
    def test_f03_two_editions_one_series(self):
        confs = build_conferences_from_raw([_raw(1, "УБС-2023"), _raw(2, "УБС-2024")])
        result = group_conferences(confs)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.values())[0].count, 2)

    def test_f03_real_api_names(self):
        raw = [
            _raw(1482, 'Всерос. школа-конференция "Управление большими системами" (УБС, Воронеж)'),
            _raw(1480, 'Всерос. школа-конференция "Управление большими системами" (УБС, Волгоград)'),
            _raw(2564, 'Межд. мультиконференция "Управление большими системами" (УБС, Москва)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('УБС', result)
        self.assertEqual(result['УБС'].count, 3)

    def test_mkpu_variants_one_series(self):
        raw = [
            _raw(1, 'мультиконференция по проблемам управления (МКПУ, Дивноморское)'),
            _raw(2, 'Всероссийская мультиконференция по проблемам управления (МКПУ, Волгоград)'),
            # третья — дочерняя, уйдёт в children, не в count
            _raw(3, 'Мультиконференция по проблемам управления (МКПУ): конференция "УАКС"'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('МКПУ', result)
        mkpu = result['МКПУ']
        # 2 самостоятельных выпуска + дочерние в children
        self.assertEqual(mkpu.count, 2)
        self.assertGreaterEqual(mkpu.total_children, 1)

    def test_dccn_three_editions(self):
        raw = [_raw(i, 'Распределенные компьютерные и телекоммуникационные сети (DCCN)')
               for i in range(3)]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('DCCN', result)
        self.assertEqual(result['DCCN'].count, 3)

    def test_same_title_different_organizer(self):
        raw = [
            _raw(1, 'научно-практическая конференция "Инжиниринг предприятий" (Москва)'),
            _raw(2, 'Российская конференция "Инжиниринг предприятий" (Москва)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        multi = [s for s in result.values() if s.count > 1]
        self.assertEqual(len(multi), 1)

    def test_different_conferences_separate(self):
        raw = [_raw(1, "УБС-2023"), _raw(2, 'Конф. (DCCN)'), _raw(3, 'Конф. (MLSD)')]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 3)


class TestF04Legacy(unittest.TestCase):
    def test_f04_unique_keys_no_grouping(self):
        raw = [_raw(i, f'Конф. (УНИ{i}КАЛ{i})') for i in range(5)]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs, fuzzy=False)
        self.assertEqual(len(result), 5)

    def test_f04_legacy_all_different_names(self):
        raw = [
            _raw(1, 'Конференция (КОПУ)'),
            _raw(2, 'Конференция (КСА)'),
            _raw(3, 'Конференция (КНС)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 3)


class TestChildConferences(unittest.TestCase):
    def test_child_attached_to_series(self):
        raw = [
            _raw(300, 'Всероссийская мультиконференция (МКПУ, Волгоград)'),
            _raw(2853, 'Мультиконференция (МКПУ): конференция УАКС'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('МКПУ', result)
        mkpu = result['МКПУ']
        self.assertEqual(mkpu.count, 1)
        self.assertGreaterEqual(mkpu.total_children, 1)

    def test_vramkakh_child_attached(self):
        raw = [
            _raw(400, 'Всероссийская мультиконференция (МКПУ, Москва)'),
            _raw(1741, 'Конференция УРСС, проводимая в рамках МКПУ'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('МКПУ', result)
        self.assertGreaterEqual(result['МКПУ'].total_children, 1)


class TestUniversalityNewAbbreviations(unittest.TestCase):
    def test_invented_abbr_groups_correctly(self):
        raw = [
            _raw(100, 'Конференция "Квантовые вычисления" (КВУП, Новосибирск)'),
            _raw(101, 'Международная конференция "Квантовые вычисления" (КВУП, Москва)'),
            _raw(102, 'Конференция "Квантовые вычисления" (КВУП-2024)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('КВУП', result)
        self.assertEqual(result['КВУП'].count, 3)

    def test_invented_abbr_dash_year(self):
        confs = build_conferences_from_raw([_raw(1, "ЗИМС-2024"), _raw(2, "ЗИМС-2025")])
        result = group_conferences(confs)
        self.assertEqual(len(result), 1)

    def test_invented_multiconf_structure(self):
        raw = [
            _raw(1, 'Суперконференция (СУПЕР, Город)'),
            _raw(2, 'Суперконференция (СУПЕР): секция А'),
            _raw(3, 'Суперконференция (СУПЕР): секция Б'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('СУПЕР', result)
        # 1 самостоятельный выпуск + секции А и Б как дочерние
        self.assertEqual(result['СУПЕР'].count, 1)
        self.assertGreaterEqual(result['СУПЕР'].total_children, 2)


class TestConferenceSeriesModel(unittest.TestCase):
    def _ubs(self):
        s = ConferenceSeries('УБС', key_type='abbr', confidence='high')
        s.editions = [
            _ed(1, 'УБС-2020', year=2020),
            _ed(2, 'УБС-2022', year=2022),
            _ed(3, 'УБС-2024', year=2024),
        ]
        return s

    def test_count(self):
        self.assertEqual(self._ubs().count, 3)

    def test_years_sorted(self):
        self.assertEqual(self._ubs().years, [2020, 2022, 2024])

    def test_year_range_multi(self):
        self.assertEqual(self._ubs().year_range, "2020–2024")

    def test_year_range_single(self):
        s = ConferenceSeries('X')
        s.editions = [_ed(1, 'X', year=2023)]
        self.assertEqual(s.year_range, "2023")

    def test_year_range_none(self):
        s = ConferenceSeries('X')
        s.editions = [_ed(1, 'X')]
        self.assertIsNone(s.year_range)

    def test_to_dict_structure(self):
        d = self._ubs().to_dict()
        for k in ('series_key', 'key_type', 'confidence', 'editions_count',
                  'year_range', 'editions'):
            self.assertIn(k, d)

    def test_to_dict_editions_desc(self):
        d = self._ubs().to_dict()
        years = [e['year'] for e in d['editions'] if e['year']]
        self.assertEqual(years, sorted(years, reverse=True))


class TestSortSeries(unittest.TestCase):
    def _map(self):
        def make(key, years):
            s = ConferenceSeries(key, key_type='abbr')
            s.editions = [_ed(i, f'{key}-{y}', year=y) for i, y in enumerate(years)]
            return key, s
        return dict([
            make('УБС',  [2020, 2021, 2022]),
            make('DCCN', [2022]),
            make('МЛСД', [2023, 2024]),
        ])

    def test_sort_count_desc(self):
        r = sort_series(self._map(), by='count', reverse=True)
        self.assertEqual(r[0].base_name, 'УБС')
        self.assertEqual(r[-1].base_name, 'DCCN')

    def test_sort_latest_desc(self):
        r = sort_series(self._map(), by='latest', reverse=True)
        self.assertEqual(r[0].base_name, 'МЛСД')

    def test_sort_name(self):
        r = sort_series(self._map(), by='name', reverse=False)
        names = [s.base_name.lower() for s in r]
        self.assertEqual(names, sorted(names))

    def test_sort_returns_all(self):
        self.assertEqual(len(sort_series(self._map())), 3)


class TestIntegration(unittest.TestCase):
    def test_full_pipeline_real_api_data(self):
        raw = [
            _raw(2037, 'Международная конференция "Управление развитием..." (MLSD)'),
            _raw(1482, 'Всерос. школа-конференция "Управление большими системами" (УБС, Воронеж)'),
            _raw(1480, 'Всерос. школа-конференция "Управление большими системами" (УБС, Волгоград)'),
            _raw(2564, 'Межд. мультиконференция "Управление большими системами" (УБС, Москва)'),
            _raw(3127, 'Распределенные компьютерные и телекоммуникационные сети (DCCN)'),
            _raw(3136, 'Распределенные компьютерные и телекоммуникационные сети (DCCN)'),
            _raw(3130, 'Распределенные компьютерные и телекоммуникационные сети (DCCN)'),
            _raw(300,  'Всероссийская мультиконференция по проблемам управления (МКПУ, Волгоград)'),
            _raw(2853, 'Мультиконференция (МКПУ): конференция УАКС'),
            _raw(1741, 'Конференция УРСС, проводимая в рамках МКПУ'),
        ]
        confs  = build_conferences_from_raw(raw)
        result = group_conferences(confs)

        self.assertIn('УБС', result)
        self.assertEqual(result['УБС'].count, 3)

        self.assertIn('DCCN', result)
        self.assertEqual(result['DCCN'].count, 3)

        self.assertIn('МКПУ', result)
        self.assertEqual(result['МКПУ'].count, 1)
        self.assertGreaterEqual(result['МКПУ'].total_children, 2)

        self.assertLess(len(result), len(raw))

    def test_regression_all_unique(self):
        raw = [_raw(i, f'Конф. (УНИ{i}КАЛ{i})') for i in range(6)]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)