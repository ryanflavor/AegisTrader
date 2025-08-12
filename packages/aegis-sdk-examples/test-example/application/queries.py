"""Queries for test-example."""

from pydantic import BaseModel


class Query(BaseModel):
    """Base query class."""

    pass


class GetUserByIdQuery(Query):
    """Get user by ID query."""

    user_id: str


class SearchUsersQuery(Query):
    """Search users query."""

    name_pattern: str | None = None
    email_pattern: str | None = None
    limit: int = 100
    offset: int = 0


class GetUserStatsQuery(Query):
    """Get user statistics query."""

    from_date: str | None = None
    to_date: str | None = None
