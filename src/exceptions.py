#!/usr/bin/env python3
import json
import os

from .models import *

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

LOCATIONS = {
    0: 865,  # "Bruin Plate",
    1: 866,  # "De Neve",
    2: 864,  # "Epicuria",
    3: 868,  # "Bruin Bowl",
    4: 867,  # "Bruin Cafe",
    5: 873,  # "Café 1919",
    6: 874,  # "Epic @ Ackerman",
    7: 872,  # "Feast",
    8: 870,  # "Rendezvous",
    9: 869,  # "The Drey",
    10: 871,  # "The Study",
}


def main():
    data = {
        LOCATIONS[0]: [
            MunchDiningHallException(
                    status=1,
                    periods=5,
                    startDate=MunchDate(y=2026, m=1, d=4)
            )
        ],

        LOCATIONS[1]: [
            MunchDiningHallException(
                    status=1,
                    periods=5,
                    startDate=MunchDate(y=2026, m=1, d=4)
            )
        ],

        LOCATIONS[2]: [
            MunchDiningHallException(
                    status=1,
                    periods=5,
                    startDate=MunchDate(y=2026, m=1, d=4)
            )
        ],

        LOCATIONS[3]: [
            MunchDiningHallException(
                    status=1,
                    periods=5,
                    startDate=MunchDate(y=2026, m=1, d=11)
            )
        ]
    }

    j = json.dumps(
            {
                int(hall): [entry.model_dump(exclude_none=True) for entry in entries]
                for hall, entries in data.items()
            }
    )

    with open(os.path.join(DATA_DIR, f"exceptions.json"), "w") as f:
        f.write(j)


if __name__ == "__main__":
    main()
