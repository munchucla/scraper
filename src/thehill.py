#!/usr/bin/env python3
import json
import logging
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from src.models import *
from src.util import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(DATA_DIR, "thehill.json")
MEAL_FILE_PREFIX = os.path.join(DATA_DIR, "meals")
MEAL_CACHE_FILE = os.path.join(MEAL_FILE_PREFIX, "_cache.json")

MEAL_EXCLUSION_LIST: List[int] = []
MEAL_CACHE: dict[int, int] = {}

BASE_URL = "https://dining.ucla.edu"
LOCATIONS = {
    "Bruin Plate": ["/bruin-plate", 865],
    "De Neve": ["/de-neve-dining", 866],
    "Epicuria": ["/epicuria-at-covel", 864],
    "Bruin Bowl": ["/bruin-bowl", 868],
    "Bruin Cafe": ["/bruin-cafe", 867],
    "Café 1919": ["/cafe-1919", 873],
    "Epic @ Ackerman": ["/epicuria-at-ackerman", 874],
    "Feast": ["/spice-kitchen", 872],
    "Rendezvous": ["/rendezvous", 870],
    "The Drey": ["/the-drey", 869],
    "The Study": ["/the-study-at-hedrick", 871],
}

ZERO_MUNCH_NUTRITION = MunchNutrition(
        servingSize=0,
        totalFat=MunchNutritionEntry(pdv=0, amt=0),
        saturatedFat=MunchNutritionEntry(pdv=0, amt=0),
        transFat=MunchNutritionEntry(pdv=0, amt=0),
        cholesterol=MunchNutritionEntry(pdv=0, amt=0),
        sodium=MunchNutritionEntry(pdv=0, amt=0),
        carbs=MunchNutritionEntry(pdv=0, amt=0),
        fiber=MunchNutritionEntry(pdv=0, amt=0),
        sugar=MunchNutritionEntry(pdv=0, amt=0),
        protein=MunchNutritionEntry(pdv=0, amt=0),
        calcium=MunchNutritionEntry(pdv=0, amt=0),
        iron=MunchNutritionEntry(pdv=0, amt=0),
        potassium=MunchNutritionEntry(pdv=0, amt=0),
        vA=MunchNutritionEntry(pdv=0, amt=0),
        vB6=MunchNutritionEntry(pdv=0, amt=0),
        vB12=MunchNutritionEntry(pdv=0, amt=0),
        vC=MunchNutritionEntry(pdv=0, amt=0),
        vD=MunchNutritionEntry(pdv=0, amt=0),
        calories=0,
        # totalFat=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # saturatedFat=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # transFat=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # cholesterol=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # sodium=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # carbs=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # fiber=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # sugar=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # protein=MunchNutritionEntry(pdv=0, amt=0, u="g"),
        # calcium=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # iron=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # potassium=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # vA=MunchNutritionEntry(pdv=0, amt=0, u="µg"),
        # vB6=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # vB12=MunchNutritionEntry(pdv=0, amt=0, u="µg"),
        # vC=MunchNutritionEntry(pdv=0, amt=0, u="mg"),
        # vD=MunchNutritionEntry(pdv=0, amt=0, u="µg"),
)

# Submit a PR if the following lists are not exhaustive or trigger false positives
# I used ChatGPT cut me some slack

PORK_MATCHES = [
    "pork", "porcine", "hog", "swine", "pig",
    "bacon", "ham", "prosciutto", "pancetta", "guanciale",
    "lard", "gelatin",
    "char siu", "tonkotsu", "chashu"
]

BEEF_MATCHES = [
    "beef", "bovine", "cow", "cattle",
    "steak", "brisket", "short rib", "ribeye",
    "sirloin", "carne asada", "bulgogi", "pastrami"
]

CHICKEN_MATCHES = [
    "chicken", "hen", "rooster", "cockerel", "broiler",
    # "chicken breast", "chicken thigh", "chicken wing",
    # "chicken leg", "chicken drumstick",
    # "chicken fat", "chicken skin",
    # "chicken broth", "chicken stock",
    # "chicken meal", "chicken powder",
    # "chicken extract", "chicken flavor",
    "poulet", "pollo", "ayam", "gai", "tori"
]


def generate_extra_labels(name: str) -> List[LABEL]:
    labels: List[LABEL] = []
    name = name.lower().strip()
    # Check for pork or gelatin or ham or any pig-stuff
    if bool(re.search(rf"\b({'|'.join(map(re.escape, PORK_MATCHES))})\b", name, re.I)):
        labels.append("Pork")
    # Check for any beef products
    if bool(re.search(rf"\b({'|'.join(map(re.escape, BEEF_MATCHES))})\b", name, re.I)):
        labels.append("Beef")
    # Check for any chicken products
    if bool(re.search(rf"\b({'|'.join(map(re.escape, CHICKEN_MATCHES))})\b", name, re.I)):
        labels.append("Chicken")
    return labels


def sanitize_name(name: str) -> str:
    name = name.strip().lower()  # Only lowercase
    s = name.split(" ")

    # Remove any words with numbers or special characters
    s = [word for word in s if not re.match(r".*[0-9].*", word) and not re.match(r".*[^a-zA-Z].*", word)]

    # Remove any of these
    ABBRS = ["oz", "lb", "ct", "select",
             "sp"]  # ["g", "kg", "ml", "l", "tbsp", "tsp", "cup", "pint", "quart", "gallon"]
    s = [word for word in s if word not in ABBRS]

    # Move any color words to the beginning of the list
    COLORS = ["red", "blue", "green", "yellow", "orange", "purple", "pink", "black", "white", "brown", "gray", "silver",
              "gold"]
    s = [word for word in s if word in COLORS] + [word for word in s if word not in COLORS]

    # Move any word ending in "ed" to the start of the list
    s = [word for word in s if re.match(r".*[Ee]d.*", word)] + [word for word in s if not re.match(r".*[Ee]d.*", word)]

    # Move any word ending in "ing" to the start of the list
    # s = [word for word in s if not re.match(r".*[Ii]ng.*", word)] + [word for word in s if re.match(r".*[Ii]ng.*", word)]
    # Move any word ending in "ly" to the start of the list
    # s = [word for word in s if not re.match(r".*[Ll]y.*", word)] + [word for word in s if re.match(r".*[Ll]y.*", word)]

    # Move any word in the following list to the start of the list
    CUSTOM_START_WORDS = ["fresh"]
    s = [word for word in s if word in CUSTOM_START_WORDS] + [word for word in s if word not in CUSTOM_START_WORDS]

    # Move any word in the following list to the end of the list
    CUSTOM_END_WORDS = ["gelato"]
    s = [word for word in s if word not in CUSTOM_END_WORDS] + [word for word in s if word in CUSTOM_END_WORDS]

    # Recreate word
    return " ".join(s).title()


def parse_dish_ingredients(soup: Tag) -> List[MunchIngredient]:
    raw_ingredients: List[Tag] = []
    parsed_ingredients: List[MunchIngredient] = []
    p = soup.select_one("p > strong")
    p_text = p.get_text(strip=True)
    if p_text == "Ingredients:":
        ul = soup.select_one("ul.nolispace")
        for li in ul.select("li"):
            raw_ingredients.append(li)
    else:
        raw_ingredients.append(p)
    for ri in raw_ingredients:
        labels: List[LABEL: str] = []
        for strong in ri.select("strong"):
            str_text = strong.get_text(strip=True)
            if str_text.startswith("Ingredients:"):
                strong.decompose()
                continue
            for lbl in str_text[1:-1].split(","):
                labels.append(lbl.strip())
            strong.decompose()
        ingredient_name = re.split(r'[:(\[]', ri.get_text(strip=True), maxsplit=1)[0].strip().title()
        ingredient_name = sanitize_name(ingredient_name)
        labels = list(set(labels)) + generate_extra_labels(ingredient_name)
        # paragraph += f"{ingredient_name} ({', '.join(labels)})"
        parsed_ingredients.append(MunchIngredient(name=ingredient_name, labels=labels))
    return parsed_ingredients


def parse_dish_nutrition(soup: Tag) -> MunchNutrition:
    mn: dict[str, int | float | MunchNutritionEntry] = dict()
    # Serving Size
    mn["servingSize"] = float(soup.find_all(string=True, recursive=False)[0].strip().replace("oz", ""))
    # Calories
    cal_parent = soup.select_one("p.single-calories")
    mn["calories"] = int(cal_parent.get_text(strip=True).lower().replace("calories", ""))
    # Tables
    all_tds: List[List[Tag]] = []
    # Table 1
    table1 = soup.select_one("table.nutritive-table")
    for row in table1.select("tr"):
        temp_tds = row.select("td")
        if len(temp_tds) >= 2:
            all_tds.append([temp_tds[0], temp_tds[1]])
    # Table 2
    table2 = soup.select_one("table.nutritive-table-two-column")
    for row in table2.select("tr"):
        temp_tds = row.select("td")
        if len(temp_tds) >= 2:
            all_tds.append([temp_tds[0], temp_tds[1]])
        if len(temp_tds) == 4:
            all_tds.append([temp_tds[2], temp_tds[3]])
    # Parsing
    for tds in all_tds:
        nv = tds[0]
        lbl_name = nv.select_one("span").get_text(strip=True)
        lbl_value_raw = nv.get_text(strip=True).replace(lbl_name, "")
        n, u = re.match(r"([\d.]+)(g|mg|µg)?$", lbl_value_raw).groups()
        # lbl_value = float(n) / (1000 if u == "mg" else 1_000_000 if u == "µg" else 1)
        # pdv = float(tds[1].get_text(strip=True).replace("%", ""))
        tds1minusperc = tds[1].get_text(strip=True).replace("%", "")
        if tds1minusperc == "":
            tds1minusperc = "0"
        pdv = int(tds1minusperc)

        key: str
        if lbl_name == "Total Fat":
            key = "totalFat"
        elif lbl_name == "Saturated Fat":
            key = "saturatedFat"
        elif lbl_name == "Trans Fat":
            key = "transFat"
        elif lbl_name == "Cholesterol":
            key = "cholesterol"
        elif lbl_name == "Sodium":
            key = "sodium"
        elif lbl_name == "Total Carbohydrate":
            key = "carbs"
        elif lbl_name == "Dietary Fiber":
            key = "fiber"
        elif lbl_name == "Sugars":
            key = "sugar"
        elif lbl_name == "Protein":
            key = "protein"
        elif lbl_name == "Calcium":
            key = "calcium"
        elif lbl_name == "Iron":
            key = "iron"
        elif lbl_name == "Potassium":
            key = "potassium"
        elif lbl_name == "Vitamin A":
            key = "vA"
        elif lbl_name == "Vitamin B6":
            key = "vB6"
        elif lbl_name == "Vitamin B12":
            key = "vB12"
        elif lbl_name == "Vitamin C":
            key = "vC"
        elif lbl_name == "Vitamin D":
            key = "vD"
        else:
            continue
        mn[key] = MunchNutritionEntry(pdv=pdv, amt=round(float(n), 2))
    return safe_parse(MunchNutrition, mn) or ZERO_MUNCH_NUTRITION


def parse_location_dishes(soup: Tag) -> List[int]:
    dishes = []
    for dish in soup.select("section.recipe-card"):
        name = dish.select_one("div.menu-item-title div.ucla-prose h3").get_text(strip=True).replace("w/ ",
                                                                                                     "w/").replace("w/",
                                                                                                                   "w/ ")
        allergen_labels = dish.select_one("div.menu-item-meta-data")
        allergens = []
        if allergen_labels:
            allergens = [label.get("title").strip().title() for label in allergen_labels.select("img")]
        link_to_meal_details = BASE_URL + dish.select_one("div.see-menu-details a").get("href").strip()
        # Format https://dining.ucla.edu/menu-item/?recipe=7361
        dish_id = int(link_to_meal_details.split("?recipe=")[1] or 0)
        dish_path = os.path.join(DATA_DIR, "meals", f"{dish_id}.json")
        if dish_id not in MEAL_CACHE or MEAL_CACHE[dish_id] is None:
            MEAL_CACHE[dish_id] = 0
        if os.path.exists(dish_path) and (dish_id not in MEAL_EXCLUSION_LIST) and (abs(MEAL_CACHE[dish_id] - int(time.time())) < 60*60*24*15):
            pass
        else:
            meal_details_bowl = BeautifulSoup(fetch(link_to_meal_details), "html.parser")
            dish_ingredients: List[MunchIngredient] = list()
            dish_nutrition: MunchNutrition
            scg = meal_details_bowl.select_one(".single-complex-grid")
            if scg:
                lis = scg.select("li")
                for li in lis:
                    text = li.select_one("a").get_text(strip=True)
                    sub_allergens = list(
                        map(lambda x: x.get("title").strip().title(), li.select("img"))) + generate_extra_labels(text)
                    dish_ingredients.append(MunchIngredient(name=text, labels=sub_allergens))
                # nutrition_div = meal_details_bowl.select_one("div#nutrition")
                dish_nutrition = ZERO_MUNCH_NUTRITION
            else:
                dish_ingredients = parse_dish_ingredients(meal_details_bowl.select_one("div#ingredient_list"))
                dish_nutrition = parse_dish_nutrition(meal_details_bowl.select_one("div#nutrition"))
            for ingredient in dish_ingredients:
                for label in ingredient.labels:
                    if label not in allergens:
                        allergens.append(label)
            dish = MunchDish(
                    name=name,
                    id=dish_id,
                    labels=allergens,
                    ingredients=dish_ingredients,
                    nutrition=dish_nutrition,
            )
            with open(dish_path, "w") as f:
                f.write(dish.model_dump_json())
                MEAL_CACHE[dish_id] = int(time.time())
        dishes.append(dish_id)
    return dishes


def parse_location_stations(soup: Tag) -> List[MunchStationMenu]:
    stations = []
    for station in soup.select("div.meal-station"):
        name = station.select_one("div.cat-heading-box .category-heading h2").get_text(strip=True)
        menu = station.select_one("div.recipe-list")
        if menu:
            dishes = parse_location_dishes(menu)
            # for dish in dishes:
            #     with open(os.path.join(DATA_DIR, "meals", f"{dish.id}.json"), "w") as f:
            #         f.write(dish.model_dump_json())
            stations.append(MunchStationMenu(name=name, dishes=dishes))
    return stations


def parse_location_meal_periods(soup: BeautifulSoup, hours: InternalMunchLocationHours) -> List[MunchMealPeriod]:
    periods = []
    scraping_info = {
        "Breakfast": {
            "selector": "#breakfastmenu.anchor-float",
            "label": "Breakfast"
        },
        "Lunch": {
            "selector": "#lunchmenu.anchor-float",
            "label": "Lunch"
        },
        "Dinner": {
            "selector": "#dinnermenu.anchor-float",
            "label": "Dinner"
        },
        "Late Night": {
            "selector": "#overnightmenu.anchor-float",
            "label": "Late Night"
        }
    }

    for meal in scraping_info:
        meal_period = soup.select_one(scraping_info[meal]["selector"])
        if meal_period:
            meal_period = meal_period.find_next_sibling()
            label_text = meal_period.select_one("h2").get_text(strip=True)
            # if label_text.lower() == scraping_info[meal]["label"].lower():
            menu_bowl = meal_period.select_one(".wp-block-columns.alignwide .at-a-glance-menu__dining-location")
            if menu_bowl:
                stations = parse_location_stations(menu_bowl)
                dumped = hours.model_dump()
                meal_period = MunchMealPeriod(
                        name=label_text.title(),  # scraping_info[meal]["label"],
                        startTime=dumped[meal]["startTime"],
                        endTime=dumped[meal]["endTime"],
                        stations=stations
                )
                periods.append(meal_period)

    # bm = soup.select_one("#breakfastmenu.anchor-float")
    # breakfast_menu = bm.find_next_sibling() if bm else None
    # if breakfast_menu:
    #     label_text = breakfast_menu.select_one("h2.fleft").get_text(strip=True)
    #     if label_text.lower() == "breakfast":
    #         menu_bowl = breakfast_menu.select_one(".wp-block-columns.alignwide .at-a-glance-menu__dining-location")
    #         if menu_bowl:
    #             stations = parse_location_stations(menu_bowl)
    #             breakfast_period = MunchMealPeriod(
    #                     name="Breakfast",
    #                     startTime=hours.Breakfast.startTime,
    #                     endTime=hours.Breakfast.endTime,
    #                     stations=stations,
    #             )
    #             periods.append(breakfast_period)
    # Breakfast
    # bm = soup.select_one("#breakfastmenu.anchor-float")
    # breakfast_menu = bm.find_next_sibling() if bm else None
    # if breakfast_menu:
    #     label_text = breakfast_menu.select_one("h2.fleft").get_text(strip=True)
    #     if label_text.lower() == "breakfast":
    #         menu_bowl = breakfast_menu.select_one(".wp-block-columns.alignwide .at-a-glance-menu__dining-location")
    #         if menu_bowl:
    #             stations = parse_location_stations(menu_bowl)
    #             breakfast_period = MunchMealPeriod(
    #                 name="Breakfast",
    #                 startTime=hours.Breakfast.startTime,
    #                 endTime=hours.Breakfast.endTime,
    #                 stations=stations,
    #             )
    #             periods.append(breakfast_period)
    # Lunch
    return periods


def parse_location_hours(soup: BeautifulSoup) -> Optional[InternalMunchLocationHours]:
    data = {}
    parent = soup.select_one(".dining-hours-container .dining-hours-list")
    if parent:
        for child in parent.select(".dining-hours-item"):
            meal_name = child.select_one("span.meal-name").get_text(strip=True)
            meal_time = child.select_one("span.meal-time").get_text(strip=True)

            # Convert "Extended Dinner" --> "Late Night"
            if meal_name == "Extended Dinner":
                meal_name = "Late Night"

            # Parse meal time into start and end given raw format: "7:00 a.m. - 10:00 a.m." or "Closed"
            if len(meal_time) > 0 and meal_time != "Closed":
                start, end = meal_time.split("-")  # "7:00 a.m. " " 10:00 a.m."
                start = start.strip().split(" ")  # "7:00" "a.m."
                end = end.strip().split(" ")  # "10:00" "a.m."
                start_time = MunchTime(h=int(start[0].split(":")[0]), m=int(start[0].split(":")[1]),
                                       z="AM" if start[1].endswith("a.m.") else "PM")
                end_time = MunchTime(h=int(end[0].split(":")[0]), m=int(end[0].split(":")[1]),
                                     z="AM" if end[1].endswith("a.m.") else "PM")
                data[meal_name] = InternalMunchLocationHoursEntry(startTime=start_time, endTime=end_time)
    return (safe_parse(InternalMunchLocationHours, data) or None) if len(data) > 0 else None


def parse_location_dates(soup: BeautifulSoup) -> List[MunchDate]:
    dates = []
    for option in soup.select("option"):
        value = option.get("value")  # YYYY-MM-DD
        if value and len(value) == 10:
            dates.append(MunchDate(y=int(value[:4]), m=int(value[5:7]), d=int(value[8:])))
    return dates


def parse_locations() -> List[MunchLocation]:
    global MEAL_CACHE
    with open(MEAL_CACHE_FILE, "r") as f:
        MEAL_CACHE = json.load(f)

    locations = []

    for loc_name, loc_data in LOCATIONS.items():
        try:
            loc_url = BASE_URL + loc_data[0]
            soup = BeautifulSoup(fetch(loc_url), "html.parser")

            # Parse hours schedule
            hours_bowl = soup.select_one(".dining-hours-summary")
            hours = (
                parse_location_hours(hours_bowl)
                if hours_bowl
                else None
            )

            # Parse future days list
            today = datetime.now(ZoneInfo("America/Los_Angeles"))
            dates_bowl = soup.select_one("select")
            dates = (
                parse_location_dates(dates_bowl)
                if dates_bowl
                else []
            )

            # Case where select is empty but today has hours
            if len(dates) == 0 and hours is not None:
                dates = [MunchDate(y=today.year, m=today.month, d=today.day)]

            # Loop over each date >= today and parse meal periods
            location_dates = []
            for date in dates:
                if date.d >= today.day:
                    location_date_soup = BeautifulSoup(fetch(loc_url + f"?date={date.y}-{date.m}-{date.d}"),
                                                       "html.parser")
                    location_date_periods = parse_location_meal_periods(location_date_soup, hours)

                    # verify we at least have what "hours" specifices for today
                    if date.d == today.day and len(location_date_periods) == 0:
                        if hours is not None:
                            for k, v in hours.model_dump().items():
                                if v is not None:
                                    location_date_periods.append(MunchMealPeriod(
                                            name=k,
                                            startTime=v["startTime"],
                                            endTime=v["endTime"],
                                            stations=[]
                                    ))

                    location_date = safe_parse(MunchLocationDate, {
                        "date": date,
                        "periods": location_date_periods,
                    })
                    if location_date:
                        location_dates.append(location_date)

            location_data = {
                "name": loc_name,
                "id": loc_data[1],
                "type": "Dining Hall" if loc_name in ["BPlate", "De Neve", "Epicuria"] else "Restaurant",
                "dates": location_dates,
            }
            location = safe_parse(MunchLocation, location_data)
            if location:
                locations.append(location)

        except Exception:
            logging.exception(f"Error parsing location {loc_name}")

    with open(MEAL_CACHE_FILE, "w") as f:
        f.write(json.dumps(MEAL_CACHE))

    return locations


def main():
    scraped = parse_locations()
    data = [json.loads(scrape.model_dump_json()) for scrape in scraped]
    j = json.dumps(data)
    with open(OUT_FILE, "w") as f:
        f.write(j)


if __name__ == "__main__":
    main()
