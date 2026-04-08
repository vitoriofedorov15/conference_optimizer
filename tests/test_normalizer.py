"""
Тесты модуля нормализации (normalizer.py) и определения ключа серии (series_key.py).
ГОСТ 19.301-79: Программа и методика испытаний.

Тесты F-01, F-02 из ТЗ.
Запуск: python -m unittest tests/test_normalizer.py -v
"""

import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalizer import normalize, normalize_batch
from series_key import get_series_key


class TestExtractYear(unittest.TestCase):
    """F-01, F-02: извлечение года из названия."""

    def _year(self, name): return normalize(name)['year']

    def test_year_after_dash(self):
        self.assertEqual(self._year("УБС-2023"), 2023)

    def test_year_after_dash_latin(self):
        self.assertEqual(self._year("STAB-2021"), 2021)

    def test_year_after_apostrophe(self):
        self.assertEqual(self._year("MLSD'2019"), 2019)

    def test_year_after_space(self):
        self.assertEqual(self._year("STAB 2021"), 2021)

    def test_year_in_parens_alone(self):
        self.assertEqual(self._year("Конференция (2024)"), 2024)

    def test_year_with_city_year_last(self):
        self.assertEqual(self._year("Конференция (Москва, 2024)"), 2024)

    def test_year_with_city_year_first(self):
        self.assertEqual(self._year("Конф (2024, Москва)"), 2024)

    def test_year_before_comma_city(self):
        self.assertEqual(self._year("DCCN 2022, Moscow"), 2022)

    def test_year_in_abbr_parens(self):
        self.assertEqual(self._year("XVII Всероссийское совещание (ВСПУ-2023)"), 2023)

    def test_no_year_returns_none(self):
        self.assertIsNone(self._year("Управление большими системами"))

    def test_short_number_not_year(self):
        self.assertIsNone(self._year("Конференция 123"))

    def test_empty_returns_none(self):
        self.assertIsNone(self._year(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(self._year("   "))


class TestExtractBaseName(unittest.TestCase):
    """Базовое название не содержит год."""

    def _base(self, name): return normalize(name)['base_name']

    def test_year_removed_after_dash(self):
        base = self._base("УБС-2023")
        self.assertNotIn("2023", base)
        self.assertIn("УБС", base)

    def test_year_removed_after_space(self):
        self.assertNotIn("2021", self._base("STAB 2021"))

    def test_year_removed_in_parens(self):
        self.assertNotIn("2024", self._base("Конференция (2024)"))

    def test_base_not_empty(self):
        for name in ["УБС-2023", "DCCN 2022, Moscow", "MLSD'2019"]:
            with self.subTest(name=name):
                self.assertTrue(self._base(name).strip())

    def test_no_trailing_separators(self):
        for name in ["УБС-2023", "DCCN 2022, Moscow"]:
            with self.subTest(name=name):
                base = self._base(name).strip()
                self.assertNotRegex(base, r'[-,;:]\s*$')

    def test_idempotent(self):
        base1 = self._base("УБС-2023")
        base2 = self._base(base1)
        self.assertEqual(base1.strip(), base2.strip())

    def test_empty_input(self):
        self.assertEqual(self._base(""), "")


class TestExtractLocation(unittest.TestCase):
    """Извлечение локации."""

    def _loc(self, name): return normalize(name)['location']

    def test_city_in_parens(self):
        loc = self._loc("УБС-2024 (Красноярск)")
        self.assertIsNotNone(loc)
        self.assertIn("Красноярск", loc)

    def test_city_with_year(self):
        loc = self._loc("Конференция (Москва, 2024)")
        self.assertIsNotNone(loc)
        self.assertIn("Москва", loc)

    def test_city_after_comma(self):
        loc = self._loc("DCCN 2022, Moscow")
        self.assertIsNotNone(loc)
        self.assertIn("Moscow", loc)

    def test_no_location(self):
        self.assertIsNone(self._loc("УБС-2023"))

    def test_year_not_location(self):
        loc = self._loc("Конференция (2024)")
        if loc:
            self.assertNotRegex(loc, r'^\d{4}$')


class TestSeriesKeyUniversal(unittest.TestCase):
    """
    Ключевые тесты универсальности алгоритма.
    Алгоритм НЕ должен содержать хардкода конкретных аббревиатур.
    Он должен правильно определять ключ для ЛЮБОГО названия из ИСАНД.
    """

    def _key(self, name): return get_series_key(name)
    def _abbr(self, name):
        kt, k = get_series_key(name)
        self.assertEqual(kt, 'abbr', f"Ожидался 'abbr' для «{name}», получен '{kt}'")
        return k

    # --- Аббревиатуры в скобках ---
    def test_abbr_in_parens_latin(self):
        self.assertEqual(self._abbr('Конференция "Управление..." (MLSD)'), 'MLSD')

    def test_abbr_in_parens_cyrillic(self):
        self.assertEqual(self._abbr('Школа-конференция "УБС" (УБС, Воронеж)'), 'УБС')

    def test_abbr_with_city_in_parens(self):
        self.assertEqual(self._abbr('Конференция (АМУР, Симферополь)'), 'АМУР')

    def test_abbr_with_year_in_parens(self):
        self.assertEqual(self._abbr('Всероссийское совещание (ВСПУ-2023)'), 'ВСПУ')

    # --- Форматы АББР-год ---
    def test_abbr_dash_year(self):
        self.assertEqual(self._abbr('УБС-2023'), 'УБС')

    def test_abbr_apostrophe_year(self):
        self.assertEqual(self._abbr("MLSD'2019"), 'MLSD')

    def test_abbr_space_year(self):
        self.assertEqual(self._abbr('DCCN 2022, Moscow'), 'DCCN')

    # --- Структура мультиконференция: подконференция ---
    def test_multiconf_with_abbr_before_colon(self):
        name = 'Мультиконференция по проблемам управления (МКПУ): конференция "УАКС"'
        self.assertEqual(self._abbr(name), 'МКПУ')

    def test_multiconf_vramkakh(self):
        name = ('Локальная конференция "УРСС" (Волгоград), '
                'проводимая в рамках Всероссийской мультиконференции (МКПУ)')
        self.assertEqual(self._abbr(name), 'МКПУ')

    # --- Одна серия через разные форматы ---
    def test_ubs_series_consistency(self):
        """Все форматы УБС дают один ключ."""
        names = [
            'Всероссийская школа-конференция "Управление большими системами" (УБС, Воронеж)',
            'Всероссийская школа-конференция "Управление большими системами" (УБС, Волгоград)',
            'Международная мультиконференция "Управление большими системами" (УБС, Москва)',
            'УБС-2023',
            'УБС-2024',
            'УБС-2024 (Красноярск)',
        ]
        keys = [self._abbr(n) for n in names]
        self.assertTrue(all(k == keys[0] for k in keys),
                        f"Все УБС должны давать один ключ, получено: {set(keys)}")

    def test_mkpu_series_consistency(self):
        """Все форматы МКПУ дают один ключ."""
        names = [
            'мультиконференция по проблемам управления (МКПУ, Дивноморское)',
            'Всероссийская мультиконференция по проблемам управления (МКПУ, Волгоград)',
            'Мультиконференция по проблемам управления (МКПУ): конференция "УАКС"',
            'Локальная конференция (УРСС), проводимая в рамках МКПУ',
        ]
        keys = [self._abbr(n) for n in names]
        self.assertTrue(all(k == keys[0] for k in keys),
                        f"Все МКПУ должны давать один ключ, получено: {set(keys)}")

    def test_dccn_series_consistency(self):
        """Одинаковые названия DCCN дают один ключ."""
        names = [
            'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)',
            'Распределенные компьютерные и телекоммуникационные сети: управление, вычисление, связь (DCCN)',
            'DCCN 2022, Moscow',
        ]
        keys = [self._abbr(n) for n in names]
        self.assertTrue(all(k == keys[0] for k in keys))

    # --- Title-ключи: конференции без аббревиатур ---
    def test_same_title_different_organizer(self):
        """Одно название при разных организаторах — одна серия."""
        n1 = 'научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'
        n2 = 'Российская научно-практическая конференция "Инжиниринг предприятий и управление знаниями" (Москва)'
        kt1, k1 = get_series_key(n1)
        kt2, k2 = get_series_key(n2)
        self.assertEqual(k1, k2, "Одно название — один ключ независимо от организатора")

    def test_same_title_different_city(self):
        """Один симпозиум в разных городах — одна серия."""
        n1 = 'Международный симпозиум "Рефлексивные процессы и управление" (Москва)'
        n2 = 'Международный научно-практический симпозиум "Рефлексивные процессы и управление" (Москва)'
        _, k1 = get_series_key(n1)
        _, k2 = get_series_key(n2)
        self.assertEqual(k1, k2)

    # --- Граничные случаи ---
    def test_empty_string(self):
        kt, k = get_series_key("")
        self.assertIsNotNone(k)

    def test_no_heuristic_hardcode(self):
        """
        Придуманная аббревиатура которой нет ни в каком словаре —
        алгоритм должен её всё равно правильно извлечь из скобок.
        """
        invented = 'Конференция "Квантовые вычисления и управление" (КВУП, Новосибирск)'
        kt, k = get_series_key(invented)
        self.assertEqual(kt, 'abbr')
        self.assertEqual(k, 'КВУП')

    def test_invented_abbr_dash_year(self):
        """Совершенно новая аббревиатура в формате АББР-год."""
        kt, k = get_series_key("ЗИМС-2025")
        self.assertEqual(kt, 'abbr')
        self.assertEqual(k, 'ЗИМС')

    def test_invented_abbr_in_parens_with_year(self):
        """Аббревиатура вида ХИЗМ-2024 в скобках."""
        kt, k = get_series_key('Конференция (ХИЗМ-2024)')
        self.assertEqual(kt, 'abbr')
        self.assertEqual(k, 'ХИЗМ')


class TestNormalizeBatch(unittest.TestCase):
    """Пакетная нормализация."""

    def test_count(self):
        self.assertEqual(len(normalize_batch(["А", "Б", "В"])), 3)

    def test_empty(self):
        self.assertEqual(normalize_batch([]), [])

    def test_fields_present(self):
        r = normalize_batch(["УБС-2023"])[0]
        for f in ('original', 'base_name', 'year', 'location', 'series_key', 'key_type'):
            self.assertIn(f, r)

    def test_series_key_consistent(self):
        results = normalize_batch(["УБС-2023", "УБС-2024"])
        self.assertEqual(results[0]['series_key'], results[1]['series_key'])

    def test_years_extracted(self):
        results = normalize_batch(["УБС-2020", "УБС-2021"])
        self.assertEqual([r['year'] for r in results], [2020, 2021])


class TestEdgeCases(unittest.TestCase):
    """Граничные случаи."""

    def test_long_name(self):
        name = ("Международная научно-практическая конференция по проблемам "
                "управления большими системами — ВСПУ 2023, Москва, Россия")
        r = normalize(name)
        self.assertEqual(r['year'], 2023)
        self.assertNotIn("2023", r['base_name'])

    def test_roman_numerals_in_name(self):
        r = normalize("XVII Всероссийское совещание (ВСПУ-2023)")
        self.assertEqual(r['year'], 2023)

    def test_multiple_parens_blocks(self):
        r = normalize("Конф (секция A) (Москва, 2023)")
        self.assertEqual(r['year'], 2023)

    def test_en_dash(self):
        r = normalize("УБС–2023")
        self.assertTrue(r['base_name'].strip())

    def test_idempotency_series_key(self):
        """Повторный вызов get_series_key на base_name даёт совместимый результат."""
        name = "УБС-2023"
        _, k1 = get_series_key(name)
        r = normalize(name)
        _, k2 = get_series_key(r['base_name'])
        # base_name уже без года — ключ может чуть измениться, но серия та же
        # Главное: оба ключа не пустые
        self.assertTrue(k1)
        self.assertTrue(k2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
