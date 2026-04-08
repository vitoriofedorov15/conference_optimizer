"""
Тесты модуля группировки конференций (grouper.py).
ГОСТ 19.301-79: Программа и методика испытаний.

Тесты F-03, F-04 из ТЗ.
Запуск: python -m unittest tests/test_grouper.py -v
"""

import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Conference, ConferenceSeries
from grouper import group_conferences, build_conferences_from_raw, sort_series


def _raw(conf_id, conf_name):
    return {'conf_id': str(conf_id), 'conf_name': conf_name}

def _conf(conf_id, conf_name, year=None, location=None, series_key='', key_type='name'):
    return Conference(
        conf_id=conf_id, conf_name=conf_name,
        year=year, location=location,
        base_name=conf_name, series_key=series_key, key_type=key_type,
    )


class TestBuildFromRaw(unittest.TestCase):
    """Конвертация сырых данных API в объекты Conference."""

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
        r = build_conferences_from_raw([_raw(1, 'Конференция "Управление..." (УБС, Москва)')])
        self.assertEqual(r[0].series_key, 'УБС')

    def test_empty(self):
        self.assertEqual(build_conferences_from_raw([]), [])

    def test_accepts_isand_format(self):
        """Принимает dict с conf_isand_id (формат ответа API)."""
        r = build_conferences_from_raw([{'conf_isand_id': 2037, 'conf_name': 'MLSD 2022'}])
        self.assertEqual(r[0].conf_id, 2037)

    def test_two_editions_same_key(self):
        raw = [_raw(1, "УБС-2023"), _raw(2, "УБС-2024")]
        r = build_conferences_from_raw(raw)
        self.assertEqual(r[0].series_key, r[1].series_key)


class TestGroupConferencesF03(unittest.TestCase):
    """F-03: 'УБС-2023' + 'УБС-2024' → одна серия с двумя выпусками."""

    def test_f03_two_editions_one_series(self):
        raw = [_raw(1, "УБС-2023"), _raw(2, "УБС-2024")]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.values())[0].count, 2)

    def test_f03_real_api_names(self):
        """Реальные названия из API — все УБС в одну серию."""
        raw = [
            _raw(1482, 'Всероссийская школа-конференция молодых учёных "Управление большими системами" (УБС, Воронеж)'),
            _raw(1480, 'Всероссийская школа-конференция молодых учёных и специалистов "Управление большими системами" (УБС, Волгоград)'),
            _raw(2564, 'Международная научно-практическая мультиконференция "Управление большими системами" (УБС, Москва)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        ubs_series = [s for s in result.values() if 'УБС' in s.base_name or 'ubs' in s.base_name.lower()]
        self.assertEqual(len(ubs_series), 1)
        self.assertEqual(ubs_series[0].count, 3)

    def test_mkpu_variants_one_series(self):
        """Разные форматы МКПУ — одна серия."""
        raw = [
            _raw(1, 'мультиконференция по проблемам управления (МКПУ, Дивноморское, Геленджик)'),
            _raw(2, 'Всероссийская мультиконференция по проблемам управления (МКПУ, Волгоград)'),
            _raw(3, 'Мультиконференция по проблемам управления (МКПУ): конференция "УАКС"'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        mkpu = [s for k, s in result.items() if k == 'МКПУ']
        self.assertEqual(len(mkpu), 1)
        self.assertEqual(mkpu[0].count, 3)

    def test_dccn_three_editions(self):
        """Три записи DCCN — одна серия."""
        raw = [
            _raw(3127, 'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
            _raw(3136, 'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
            _raw(3130, 'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.values())[0].count, 3)

    def test_same_title_different_organizer(self):
        """Одно название при разных организаторах — одна серия."""
        raw = [
            _raw(2916, 'научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'),
            _raw(3166, 'Российская научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        inzh = [s for s in result.values() if s.count > 1]
        self.assertEqual(len(inzh), 1, "Две записи с одним названием должны быть в одной серии")

    def test_different_conferences_separate(self):
        """Разные конференции не объединяются."""
        raw = [
            _raw(1, "УБС-2023"),
            _raw(2, 'Конференция "Рефлексивные процессы и управление" (Москва)'),
            _raw(3, 'Конференция "MLSD 2022" (MLSD)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 3)


class TestGroupConferencesF04(unittest.TestCase):
    """F-04: Режим 'как сейчас' — каждая запись отдельно."""

    def test_f04_unique_keys_no_grouping(self):
        """Если у каждой конф уникальный ключ — N серий из N конф."""
        confs = [
            _conf(i, f"Уникальная конференция {i}", series_key=f"UNIQUE{i}", key_type='abbr')
            for i in range(5)
        ]
        result = group_conferences(confs, fuzzy=False)
        self.assertEqual(len(result), 5)
        for s in result.values():
            self.assertEqual(s.count, 1)

    def test_f04_legacy_all_different_names(self):
        """Конференции с разными названиями не группируются."""
        raw = [
            _raw(1, 'Конференция "Оптимальное управление" (КОПУ)'),
            _raw(2, 'Конференция "Системный анализ" (КСА)'),
            _raw(3, 'Конференция "Нейронные сети" (КНС)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 3)


class TestUniversalityNewAbbreviations(unittest.TestCase):
    """
    Универсальность: алгоритм работает с произвольными аббревиатурами.
    Эти аббревиатуры намеренно выдуманы и отсутствуют в любом словаре.
    """

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
        raw = [_raw(1, "ЗИМС-2024"), _raw(2, "ЗИМС-2025")]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.values())[0].count, 2)

    def test_invented_multiconf_structure(self):
        raw = [
            _raw(1, 'Суперконференция (СУПЕР): подконференция "Секция А" (СЕКА)'),
            _raw(2, 'Суперконференция (СУПЕР): подконференция "Секция Б" (СЕКБ)'),
            _raw(3, 'Суперконференция (СУПЕР, Город)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertIn('СУПЕР', result)
        self.assertEqual(result['СУПЕР'].count, 3)


class TestConferenceSeriesModel(unittest.TestCase):
    """Тесты модели ConferenceSeries."""

    def _ubs_series(self):
        return ConferenceSeries('УБС', key_type='abbr', editions=[
            _conf(1, "УБС-2020", year=2020, series_key='УБС', key_type='abbr'),
            _conf(2, "УБС-2022", year=2022, series_key='УБС', key_type='abbr'),
            _conf(3, "УБС-2024", year=2024, series_key='УБС', key_type='abbr'),
        ])

    def test_years_sorted(self):
        self.assertEqual(self._ubs_series().years, [2020, 2022, 2024])

    def test_count(self):
        self.assertEqual(self._ubs_series().count, 3)

    def test_year_range_multi(self):
        self.assertEqual(self._ubs_series().year_range, "2020–2024")

    def test_year_range_single(self):
        s = ConferenceSeries('X', editions=[_conf(1, "X-2023", year=2023, series_key='X')])
        self.assertEqual(s.year_range, "2023")

    def test_year_range_none(self):
        s = ConferenceSeries('X', editions=[_conf(1, "X", series_key='X')])
        self.assertIsNone(s.year_range)

    def test_to_dict_structure(self):
        d = self._ubs_series().to_dict()
        for f in ('series_key', 'key_type', 'editions_count', 'year_range', 'editions'):
            self.assertIn(f, d)

    def test_to_dict_editions_desc(self):
        d = self._ubs_series().to_dict()
        years = [e['year'] for e in d['editions'] if e['year']]
        self.assertEqual(years, sorted(years, reverse=True))


class TestSortSeries(unittest.TestCase):
    """Сортировка серий."""

    def _map(self):
        def make(key, years):
            s = ConferenceSeries(key, key_type='abbr')
            s.editions = [_conf(i, f"{key}-{y}", year=y, series_key=key) for i, y in enumerate(years)]
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
    """Интеграционные тесты: от реальных данных API до сгруппированных серий."""

    def test_full_pipeline_real_api_data(self):
        """Данные из реального запроса ?name=управление."""
        raw = [
            _raw(2037,  'Международная конференция "Управление развитием крупномасштабных систем" (MLSD)'),
            _raw(1482,  'Всероссийская школа-конференция молодых учёных "Управление большими системами" (УБС, Воронеж)'),
            _raw(3127,  'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
            _raw(3136,  'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
            _raw(3130,  'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)'),
            _raw(2691,  'Международная школа-симпозиум "Анализ, моделирование, управление, развитие..." (АМУР, Симферополь)'),
            _raw(2692,  'Международная школа-симпозиум Анализ, Моделирование, Управление... (АМУР, Севастополь)'),
            _raw(1473,  'Всероссийская школа-симпозиум "Анализ, моделирование, управление..." (АМУР, Симферополь)'),
            _raw(2916,  'научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'),
            _raw(3166,  'Российская научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'),
            _raw(2780,  'Международный симпозиум "Рефлексивные процессы и управление" (Москва)'),
            _raw(2734,  'Международный научно-практический симпозиум "Рефлексивные процессы и управление" (Москва)'),
            _raw(2853,  'Мультиконференция по проблемам управления (МКПУ): конференция "Управление в аэрокосм. системах" (УАКС)'),
            _raw(None,  'мультиконференция по проблемам управления (МКПУ, Дивноморское, Геленджик)'),
            _raw(None,  'Всероссийская мультиконференция по проблемам управления (МКПУ, Волгоград)'),
        ]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        sorted_list = sort_series(result, by='count', reverse=True)

        # DCCN: 3 выпуска
        self.assertIn('DCCN', result)
        self.assertEqual(result['DCCN'].count, 3)

        # АМУР: 3 выпуска
        self.assertIn('АМУР', result)
        self.assertEqual(result['АМУР'].count, 3)

        # МКПУ: 3 выпуска
        self.assertIn('МКПУ', result)
        self.assertEqual(result['МКПУ'].count, 3)

        # Инжиниринг: 2 выпуска (title-ключ)
        inzh = [s for s in result.values() if s.count == 2 and 'инжиниринг' in s.base_name.lower()]
        self.assertEqual(len(inzh), 1)

        # Рефлексивные процессы: 2 выпуска (title-ключ)
        reflex = [s for s in result.values() if 'рефлекс' in s.base_name.lower()]
        if reflex:
            self.assertEqual(reflex[0].count, 2)

        # Итого меньше записей чем было
        self.assertLess(len(result), len(confs))

    def test_regression_all_unique(self):
        """Регрессия F-04: все уникальные → N серий = N конф."""
        raw = [_raw(i, f'Конф "Тема {i}" (КОН{i})') for i in range(6)]
        confs = build_conferences_from_raw(raw)
        result = group_conferences(confs)
        self.assertEqual(len(result), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
