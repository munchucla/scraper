#!/usr/bin/env python3
import json
import logging
import os
import re

from bs4 import BeautifulSoup, Tag

from .models import *
from .util import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

LINKS = {
    "19P": "https://ask.housing.ucla.edu/app/answers/detail/a_id/1457/kw/meal%20plans/session/L3RpbWUvMTYzMjQzNzg5NC9zaWQvYlBEeTdSbHA%3D",
    "14P": "https://ask.housing.ucla.edu/app/answers/detail/a_id/1484/kw/meal%20plans/related/1",
    "11P": "https://ask.housing.ucla.edu/app/answers/detail/a_id/1726/kw/meal%20plans/related/1",
}

MAP_MONTH_TO_NUM = {
    # There's gotta be a better way to do this
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

MAP_PERIOD_TO_NUM = {
    "breakfast": 1,
    "lunch": 3,
    "dinner": 5,
}


def main():
    data = []
    quarter: Optional[Literal["Fall", "Winter", "Spring"]] = None

    for key, value in LINKS.items():
        soup = BeautifulSoup(fetch(value), "html.parser")
        body = soup.select_one("div[itemprop=\"articleBody\"]")
        ps = body.select("p")
        p0 = ps[0].get_text(strip=True)
        s = [x.strip() for x in p0.split(".")]
        m = re.search(r".+(11|14|19)P[A-Za-z\s]+(\d+)[A-Za-z\s]+", s[0])
        level = int(m.group(1))
        total = int(m.group(2))
        p2 = ps[2].get_text(strip=True)
        m2 = re.search(
            r".+(Fall|Winter|Spring).+(breakfast|lunch|dinner).+(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4}).+(breakfast|lunch|dinner).+(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})",
            p2)
        quarter = m2.group(1)
        start_date = MunchDate(y=int(m2.group(5)), m=MAP_MONTH_TO_NUM[m2.group(3)], d=int(m2.group(4)))
        end_date = MunchDate(y=int(m2.group(9)), m=MAP_MONTH_TO_NUM[m2.group(7)], d=int(m2.group(8)))
        data.append(MunchMealPlan(amt=int(key.replace("P", "")), type="P", startPeriod=MAP_PERIOD_TO_NUM[m2.group(2)],
                                  startDate=start_date, endPeriod=MAP_PERIOD_TO_NUM[m2.group(6)], endDate=end_date,
                                  totalSwipes=total))

    if not quarter:
        logging.error("Quarter not found")
        return

    j = json.dumps([json.loads(entry.model_dump_json()) for entry in data])
    with open(os.path.join(DATA_DIR, f"mealswipes-{quarter.lower()}.json"), "w") as f:
        f.write(j)


if __name__ == "__main__":
    main()
