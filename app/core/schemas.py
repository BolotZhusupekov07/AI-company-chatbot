"""Shared API schemas."""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Select, asc, desc

from app.infrastructure.db.database import Base

type SortingOrder = Literal["asc", "desc"]


class BaseListSorting(BaseModel):
    """Base list sorting query parameters."""

    sort_by: str = Field(description="Sorting field")
    sort_order: SortingOrder = Field(default="desc", description="Sorting direction")

    def sort_query(self, query: Select, model: type[Base]) -> Select:
        """Apply sorting to a SQLAlchemy select query."""

        direction = asc if self.sort_order == "asc" else desc
        if not hasattr(model, self.sort_by):
            raise ValueError(f"Invalid sort field: {self.sort_by}")
        order_column = getattr(model, self.sort_by)
        return query.order_by(direction(order_column))
