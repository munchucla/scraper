from typing import List, Optional, Literal, Annotated
from pydantic import BaseModel, Field

LABEL = Literal[
    "Vegetarian", "Vegan", "Gluten", "Dairy", "Eggs", "Wheat", "Halal", "Soy", "Sesame", "Peanut", "Alcohol", "Fish", "Crustacean-Shellfish", "Tree-Nuts", "Low-Carbon", "High-Carbon", "Pork", "Beef", "Chicken"]


# ---- Time / Date ----

class MunchTime(BaseModel):
    h: Annotated[int, Field(strict=True, ge=1, le=12)]
    m: Annotated[int, Field(strict=True, ge=0, le=59)]
    z: Literal["AM", "PM"]


class MunchDate(BaseModel):
    y: Annotated[int, Field(strict=True, ge=2020)]
    m: Annotated[int, Field(strict=True, ge=1, le=12)]
    d: Annotated[int, Field(strict=True, ge=1, le=31)]


# ---- Ingredients / Nutrition ----

class MunchNutritionEntry(BaseModel):
    pdv: Annotated[int, Field(strict=True, ge=0)]
    amt: Annotated[float, Field(strict=True, ge=0)]
    # u: Literal["g", "mg", "µg"]


class MunchNutrition(BaseModel):
    servingSize: Annotated[float, Field(strict=True, ge=0)]
    totalFat: MunchNutritionEntry
    saturatedFat: MunchNutritionEntry
    transFat: MunchNutritionEntry
    cholesterol: MunchNutritionEntry
    sodium: MunchNutritionEntry
    carbs: MunchNutritionEntry
    fiber: MunchNutritionEntry
    sugar: MunchNutritionEntry
    protein: MunchNutritionEntry
    calcium: MunchNutritionEntry
    iron: MunchNutritionEntry
    potassium: MunchNutritionEntry
    vA: Optional[MunchNutritionEntry]
    vB6: Optional[MunchNutritionEntry]
    vB12: Optional[MunchNutritionEntry]
    vC: Optional[MunchNutritionEntry]
    vD: Optional[MunchNutritionEntry]
    calories: Annotated[int, Field(strict=True, ge=0)]


class MunchIngredient(BaseModel):
    name: str
    labels: List[LABEL] = Field(min_length=0)


# ---- Dish / Menu ----

class MunchDish(BaseModel):
    name: str
    id: int
    labels: List[LABEL] = Field(min_length=0)
    ingredients: List[MunchIngredient]
    nutrition: MunchNutrition


class MunchStationMenu(BaseModel):
    name: str
    dishes: List[MunchDish] = Field(min_length=1)


class MunchMealPeriod(BaseModel):
    name: str
    startTime: MunchTime
    endTime: MunchTime
    stations: List[MunchStationMenu] = Field(min_length=0)


class MunchLocationDate(BaseModel):
    date: MunchDate
    periods: List[MunchMealPeriod] = Field(min_length=0)


class MunchLocation(BaseModel):
    name: str
    id: int
    type: Literal["Dining Hall", "Restaurant", "Food Truck"]
    dates: List[MunchLocationDate] = Field(min_length=0)


# ---- Internal Hours ----

class InternalMunchLocationHoursEntry(BaseModel):
    startTime: MunchTime
    endTime: MunchTime


class InternalMunchLocationHours(BaseModel):
    Breakfast: Optional[InternalMunchLocationHoursEntry] = None
    Lunch: Optional[InternalMunchLocationHoursEntry] = None
    Dinner: Optional[InternalMunchLocationHoursEntry] = None
    Late_Night: Optional[InternalMunchLocationHoursEntry] = Field(
            default=None, alias="Late Night"
    )

    class Config:
        populate_by_name = True


##########################################################################################

class MunchMealPlan(BaseModel):
    amt: int
    type: Literal["P", "R"]
    # quarter: Literal["Fall", "Winter", "Spring"]
    startPeriod: int  # Literal["breakfast", "lunch", "dinner"]
    startDate: MunchDate
    endPeriod: int  # Literal["breakfast", "lunch", "dinner"]
    endDate: MunchDate
    totalSwipes: int


##########################################################################################

class MunchDiningHallException(BaseModel):
    status: Literal[0, 1]  # 0 = closed, 1 = open
    periods: Literal[1, 3, 5, 4, 6, 8, 9]  # combos of 1, 3, 5 (breakfast, lunch, dinner) similar to UNIX perms
    startDate: Optional[MunchDate] = None
    endDate: Optional[MunchDate] = None
    specifics: Optional[List[MunchDate]] = None
