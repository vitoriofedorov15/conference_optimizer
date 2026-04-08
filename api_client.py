"""
Клиент для взаимодействия с REST API ИСАНД v2.5.

Базовый URL: http://193.232.208.28/api/v2.5/

Документация: Описание REST API v2.5.4
"""

import time
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode, quote

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import json as _json

logger = logging.getLogger(__name__)

BASE_URL = "http://193.232.208.28/api/v2.5"
DEFAULT_TIMEOUT = 30       # секунд
DEFAULT_RETRY = 3          # попыток
RETRY_DELAY = 2.0          # секунд между попытками


class ISANDApiError(Exception):
    """Ошибка при обращении к API ИСАНД."""
    pass


class ISANDApiClient:
    """
    Клиент REST API ИСАНД v2.5.

    Примеры использования:
        client = ISANDApiClient()
        conferences = client.search_conferences(name="управление")
        info = client.get_conference_info(conf_id=1999)
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRY,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def _get(self, endpoint: str, params: dict = None) -> Any:
        """
        Выполняет GET-запрос к API с повторными попытками.

        Parameters
        ----------
        endpoint : str
            Путь относительно base_url (например '/conferences/search').
        params : dict, optional
            Параметры строки запроса.

        Returns
        -------
        Parsed JSON response (list или dict).
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params:
            # Фильтруем None-значения
            params = {k: v for k, v in params.items() if v is not None}

        last_error = None
        for attempt in range(self.retries):
            try:
                logger.debug(f"GET {url} params={params} (attempt {attempt + 1})")

                if HAS_REQUESTS:
                    resp = requests.get(url, params=params, timeout=self.timeout)
                    resp.raise_for_status()
                    return resp.json()
                else:
                    # Fallback на urllib
                    full_url = url
                    if params:
                        full_url += "?" + urlencode(params)
                    req = urllib.request.Request(full_url)
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        raw = resp.read().decode("utf-8")
                        return _json.loads(raw)

            except Exception as e:
                last_error = e
                logger.warning(f"Ошибка запроса (попытка {attempt + 1}): {e}")
                if attempt < self.retries - 1:
                    time.sleep(RETRY_DELAY)

        raise ISANDApiError(f"Запрос к API не выполнен после {self.retries} попыток: {last_error}")

    # ------------------------------------------------------------------
    # Методы для конференций (раздел 5 API v2.5)
    # ------------------------------------------------------------------

    def get_conference_id_types(self) -> dict:
        """GET /conferences/get_ids — типы идентификаторов конференции."""
        return self._get("conferences/get_ids")

    def search_conferences(
        self,
        conf_id: int = None,
        name: str = None,
        issn: str = None,
        eissn: str = None,
        isbn: str = None,
        open_alex: str = None,
        count_only: bool = False,
    ) -> List[Dict]:
        """
        GET /conferences/search — поиск конференций по параметрам.

        Если указан идентификатор (conf_id/issn/eissn/isbn/open_alex),
        остальные параметры игнорируются (поведение API).

        Parameters
        ----------
        conf_id : int
            Идентификатор конференции в ИСАНД.
        name : str
            Название (или его часть) для поиска.
        count_only : bool
            Если True — возвращает только количество результатов.

        Returns
        -------
        list of dict  (или [{"count": N}] при count_only=True)
        """
        params = {
            "id": conf_id,
            "name": name,
            "issn": issn,
            "eissn": eissn,
            "isbn": isbn,
            "openAlex": open_alex,
        }
        if count_only:
            params["count"] = 1
        return self._get("conferences/search", params)

    def get_conference_info(self, conf_id: int) -> List[Dict]:
        """
        GET /conferences/card/get_info — подробная информация о конференции.

        Parameters
        ----------
        conf_id : int
            Идентификатор конференции в ИСАНД.
        """
        return self._get("conferences/card/get_info", {"id": conf_id})

    def get_conference_publications(
        self,
        conf_id: int,
        count_only: bool = False,
    ) -> List[Dict]:
        """
        GET /conferences/card/get_publications — публикации конференции.

        Parameters
        ----------
        conf_id : int
            Идентификатор конференции в ИСАНД.
        count_only : bool
            Если True — возвращает только количество.
        """
        params = {"id": conf_id}
        if count_only:
            params["count"] = 1
        return self._get("conferences/card/get_publications", params)

    def get_conference_authors(self, conf_id: int) -> List[Dict]:
        """GET /conferences/card/get_authors — авторы конференции."""
        return self._get("conferences/card/get_authors", {"id": conf_id})

    def get_conferences_count(self) -> int:
        """GET /conferences/analysis/get_count — общее количество конференций."""
        result = self._get("conferences/analysis/get_count")
        if isinstance(result, list) and result:
            return result[0].get("count", 0)
        return 0

    def get_conference_activity(
        self,
        conf_id: int,
        begin_year: int = None,
        end_year: int = None,
    ) -> List[Dict]:
        """GET /conferences/analysis/get_activity — активность по годам."""
        params = {"id": conf_id, "begin_year": begin_year, "end_year": end_year}
        return self._get("conferences/analysis/get_activity", params)

    # ------------------------------------------------------------------
    # Удобный метод: загрузить все конференции постранично
    # ------------------------------------------------------------------

    def fetch_all_conferences(
        self,
        name_query: str = None,
        max_results: int = None,
    ) -> List[Dict]:
        """
        Загружает конференции из API.

        Примечание: API не поддерживает пагинацию напрямую, поэтому
        для получения большого объёма используйте CSV-данные.

        Parameters
        ----------
        name_query : str, optional
            Фильтр по названию.
        max_results : int, optional
            Ограничение на количество результатов.

        Returns
        -------
        list of dict
        """
        results = self.search_conferences(name=name_query)
        if max_results is not None:
            results = results[:max_results]
        return results

    def is_available(self) -> bool:
        """Проверяет доступность API."""
        try:
            self.get_conferences_count()
            return True
        except Exception:
            return False
