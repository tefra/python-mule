import logging
import operator

import requests
from cachetools import TTLCache, cachedmethod
from cachetools.keys import hashkey

from search.models import (
    ResourceCarrier,
    ResourceCabinClass,
    ResourceLocation,
    ResourceEquipment,
    SearchResponse,
)

logger = logging.getLogger(__name__)


class ResourceManager:
    ENDPOINT = "http://127.0.0.1:8000/resources"
    ROUTES = {
        ResourceCarrier: "airlines",
        ResourceCabinClass: None,
        ResourceLocation: "airports",
        ResourceEquipment: None,
    }

    def __init__(self, ttl=3600, cachesize=10000):
        self.cache = TTLCache(ttl=ttl, maxsize=cachesize)

    def enrich(self, response: SearchResponse):
        for data in response.data:
            for clazz, resources in data.resources.all():
                codes = resources.keys()
                fetch_codes = self.filter_codes(codes)
                self.fetch(clazz, response.locale, fetch_codes)

                for code in codes:
                    resources[code] = self.get(clazz, response.locale, code)

    @cachedmethod(operator.attrgetter("cache"))
    def get(self, clazzz, locale, code):
        return self.fetch(clazzz, locale, code)

    def filter_codes(self, clazzz, locale, codes):
        if not codes:
            return []

        if not isinstance(codes, list):
            codes = [codes]

        def exists(code):
            key = hashkey(self, clazzz, locale, code)
            return key not in self.cache

        return list(filter(exists, codes))

    def fetch(self, clazzz, locale, code):
        if not code:
            return

        try:
            url = "{}/{}/".format(self.ENDPOINT, self.ROUTES.get(clazzz))
            resp = requests.get(url=url, params=dict(code=code))
            resp.raise_for_status()
            result = resp.json()

            for r in result:
                obj = clazzz.deserialize(r)
                key = hashkey(self, clazzz, locale, obj.code)
                self.cache[key] = obj

            if len(result) == 1:
                return self.cache[key]
        except Exception as e:
            logger.exception(repr(e))
