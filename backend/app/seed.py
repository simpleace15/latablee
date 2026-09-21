# Seed data command: ~12 sample recipes + a sample week — for demos/WAF testing.
# Never runs automatically in production: explicit `python -m app.seed` or admin button.
import json
from datetime import date, timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.core.security import hash_password
from app.db.engine import get_engine
from app.models import Household, MealPlanEntry, Recipe, ShoppingList, ShoppingListItem, User

SEED_FILE = Path(__file__).parent / "seed_data.json"


def seed(household_name: str = "Demo Household", admin_name: str = "Admin",
         password: str = "latablee-demo") -> dict:
    """Load sample data. Overwrites nothing — adds a demo household if the DB is empty."""
    from app.db.engine import create_all

    create_all()  # safe when tables already exist; required on a fresh DB via `python -m app.seed`
    engine = get_engine()
    with Session(engine) as session:
        existing = session.exec(select(Household)).first()
        if existing is not None:
            return {"seeded": False, "reason": "Database already has data"}
        data = json.loads(SEED_FILE.read_text())
        household = Household(
            name=household_name,
            timezone="America/Denver",
            dietary_preferences={},
            allergies=[],
            dislikes=["olives"],
            favorites=["tacos", "pasta"],
            things_to_remember="Kids like mild flavors; keep weeknight dinners under 45 min.",
            onboarded_at=None,
        )
        session.add(household)
        session.commit()
        session.refresh(household)
        admin = User(public_id="seed-admin", name=admin_name, role="admin",
                     household_id=household.id,
                     password_hash=hash_password(password))
        session.add(admin)
        session.commit()
        session.refresh(admin)
        recipes: list[Recipe] = []
        for item in data["recipes"]:
            r = Recipe(
                title=item["title"], description=item.get("description", ""),
                servings=item.get("servings", 4),
                prep_minutes=item.get("prep_minutes"), cook_minutes=item.get("cook_minutes"),
                total_minutes=(item.get("prep_minutes") or 0) + (item.get("cook_minutes") or 0) or None,
                instructions=item.get("instructions", []),
                ingredients=item.get("ingredients", []),
                tags=item.get("tags", []),
                created_by=admin.id, household_id=household.id,
            )
            from app.services.recipe_search import index_search_text

            r.search_text = index_search_text(r)
            session.add(r)
            recipes.append(r)
        session.commit()
        # sample week: dinners Mon-Fri + one weekend lunch
        monday = date.today() - timedelta(days=date.today().weekday())
        plan_slots = ["dinner"] * 5 + ["lunch"]
        plan_days = [monday + timedelta(days=i) for i in range(5)] + [monday + timedelta(days=6)]
        for i, recipe in enumerate(recipes[:6]):
            entry = MealPlanEntry(household_id=household.id, recipe_id=recipe.id,
                                  planned_date=plan_days[i], slot=plan_slots[i])
            session.add(entry)
        lst = ShoppingList(name="Groceries", household_id=household.id)
        session.add(lst)
        session.commit()
        session.refresh(lst)
        sample_items = ["milk", "eggs", "bread", "chicken thighs", "basil", "parmesan"]
        for name in sample_items:
            session.add(ShoppingListItem(list_id=lst.id, name=name, manual=True))
        session.commit()
        return {"seeded": True, "recipes": len(recipes), "admin_user": admin_name,
                "password": "(the demo password you passed)"}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Load LaTablée demo data (only on an empty database)")
    p.add_argument("--household", default="Demo Household")
    p.add_argument("--admin-name", default="Admin")
    p.add_argument("--password", default="latablee-demo")
    args = p.parse_args()
    print(json.dumps(seed(household_name=args.household, admin_name=args.admin_name, password=args.password), indent=2))
