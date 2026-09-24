# Single household, multiple users (v1 decision). One Household row per deployment.
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)  # aware; SQLite stores naive — use _aware_utc to compare


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


def _aware_utc(d: datetime | None) -> datetime | None:
    """Normalize naive datetimes to UTC-aware for comparisons (SQLite returns naive)."""
    if d is not None and d.tzinfo is None:
        return d.replace(tzinfo=UTC)
    return d


class Household(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    timezone: str = "UTC"  # IANA name; "tonight"/"Wednesday" resolve against this
    # Onboarding profile — feeds AI suggestions
    dietary_preferences: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    allergies: list[str] | None = Field(default=None, sa_column=Column(JSON))
    dislikes: list[str] | None = Field(default=None, sa_column=Column(JSON))
    favorites: list[str] | None = Field(default=None, sa_column=Column(JSON))
    # Free-text planning rules fed to the AI planner, e.g. "only 1 chicken meal a week",
    # "don't repeat any meals from the last 2 weeks" — variety knobs (0.5.1).
    planning_rules: list[str] | None = Field(default=None, sa_column=Column(JSON))
    things_to_remember: str = ""
    onboarded_at: datetime | None = None


class User(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)  # JWT sub — no email/username leaking IDs
    name: str
    role: str = "user"  # 'admin' | 'user'
    household_id: int | None = Field(default=None, foreign_key="household.id")
    password_hash: str = ""
    disabled: bool = False


class ApiToken(TimestampMixin, SQLModel, table=True):
    """Long-lived device tokens for integrations (Home Assistant, scripts).
    Only the SHA-256 hash is stored; the raw token is shown once at creation."""

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    name: str
    user_id: int = Field(foreign_key="user.id", index=True)
    household_id: int | None = Field(default=None, foreign_key="household.id")
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class InviteLink(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    household_id: int = Field(foreign_key="household.id", index=True)
    created_by: int = Field(foreign_key="user.id")
    used_at: datetime | None = None
    expires_at: datetime | None = None


class Recipe(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: str = ""
    servings: int = 4
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    total_minutes: int | None = None
    instructions: list[Any] | None = Field(default=None, sa_column=Column(JSON))  # ordered steps
    # Ingredients stored as canonical quantity units (Pint-normalized) for consolidation
    ingredients: list[Any] | None = Field(default=None, sa_column=Column(JSON))
    # no btree index on JSON (invalid in Postgres); search uses search_text
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    source_url: str | None = None
    source_name: str | None = None
    image_path: str | None = None  # relative path under data/images, served by the app
    is_favorite: bool = False  # hearted by the household — favorites filter & suggestions bias
    created_by: int | None = Field(default=None, foreign_key="user.id")
    household_id: int | None = Field(default=None, foreign_key="household.id", index=True)
    search_text: str = ""  # denormalized for SQLite FTS-style LIKE search


class Ingredient(SQLModel):
    """Embedded ingredient of a recipe (JSON column, validated by Pydantic)."""

    quantity: float | None = None  # canonical unit after normalization
    unit: str | None = None  # Pint-canonical name, e.g. 'gram', 'liter', 'piece'
    name: str
    note: str | None = None
    raw: str | None = None  # original text, shown in UI edit mode


class MealPlanEntry(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id", index=True)
    recipe_id: int | None = Field(default=None, foreign_key="recipe.id")
    # date the meal is planned for (household-local); slot: breakfast|lunch|dinner|other
    planned_date: date = Field(index=True)
    slot: str = "dinner"
    notes: str = ""
    # freeform meals don't need a recipe
    title_override: str | None = None


class ShoppingList(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = "Groceries"
    household_id: int = Field(foreign_key="household.id", index=True)


class ShoppingListItem(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    list_id: int = Field(foreign_key="shoppinglist.id", index=True)
    name: str = Field(index=True)
    quantity: float | None = None
    unit: str | None = None  # canonical
    done: bool = False
    from_recipe_ids: list[int] | None = Field(default=None, sa_column=Column(JSON))
    manual: bool = True


class WebhookEvent(TimestampMixin, SQLModel, table=True):
    """Delivered events for integrations (repo 2 clients poll or subscribe)."""

    id: int | None = Field(default=None, primary_key=True)
    event: str  # e.g. meal_plan_updated, shopping_list_updated
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    delivered_at: datetime | None = None


class ReelDraftCache(TimestampMixin, SQLModel, table=True):
    """Finished reel-import drafts keyed by normalized video URL (TTL one day).
    Makes retries idempotent — a re-submit of the same reel skips download+transcribe."""

    id: int | None = Field(default=None, primary_key=True)
    url_key: str = Field(unique=True, index=True)
    source_url: str
    draft: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class Setting(TimestampMixin, SQLModel, table=True):
    """Runtime-editable app settings (LLM config, feature flags). Admin-managed."""

    key: str = Field(primary_key=True)
    value: Any | None = Field(default=None, sa_column=Column(JSON))
