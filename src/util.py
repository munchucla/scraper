import logging
import time
from typing import Type, TypeVar, Optional

import requests
from pydantic import ValidationError, BaseModel

USER_AGENT = "MunchScraper/1.0 (+https://github.com/munchucla/scraper)"
HEADERS = {"User-Agent": USER_AGENT}


def fetch(url, max_retries=3, backoff=2):
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(0.25)
            logging.info(f"Attempt {attempt} to fetch {url}")
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logging.warning(f"Fetch attempt {attempt} failed for {url}: {e}")
            if attempt == max_retries:
                raise
            time.sleep(backoff * attempt)
    raise RuntimeError("unreachable")


T = TypeVar("T", bound=BaseModel)


def safe_parse(model: Type[T], data: dict) -> Optional[T]:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        logging.error(f"Validation failed for {model.__name__}:\n{e}")
        return None
