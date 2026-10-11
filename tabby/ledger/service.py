"""Business rules for groups, members and expenses."""

import sqlite3

from tabby.accounts import interface as accounts
from tabby.errors import Conflict, Forbidden, InvalidInput, NotFound
from tabby.ledger import repository
from tabby.ledger.splits import compute_shares


def _require_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> sqlite3.Row:
    group = repository.get_group(conn, group_id)
    if group is None:
        raise NotFound("group not found")
    if not repository.is_member(conn, group_id, user_id):
        raise Forbidden("you are not a member of this group")
    return group


def _require_friend(conn: sqlite3.Connection, user_id: int, other_id: int) -> None:
    if not accounts.are_friends(conn, user_id, other_id):
        raise InvalidInput(f"user {other_id} is not one of your friends")


def create_group(
    conn: sqlite3.Connection, creator_id: int, name: str, member_ids: list[int]
) -> dict:
    name = name.strip()
    if not name:
        raise InvalidInput("group name must not be empty")
    others = set(member_ids) - {creator_id}
    for member_id in others:
        _require_friend(conn, creator_id, member_id)
    with conn:
        group_id = repository.insert_group(conn, name)
        for member_id in sorted(others | {creator_id}):
            repository.insert_member(conn, group_id, member_id)
    return get_group(conn, group_id, creator_id)


def list_groups(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    return [dict(row) for row in repository.list_groups_for_user(conn, user_id)]


def get_group(conn: sqlite3.Connection, group_id: int, user_id: int) -> dict:
    group = _require_member(conn, group_id, user_id)
    members = accounts.get_users(conn, repository.list_member_ids(conn, group_id))
    return dict(group) | {"members": members}


def add_member(conn: sqlite3.Connection, group_id: int, actor_id: int, user_id: int) -> dict:
    _require_member(conn, group_id, actor_id)
    if repository.is_member(conn, group_id, user_id):
        raise Conflict("already a member of this group")
    _require_friend(conn, actor_id, user_id)
    with conn:
        repository.insert_member(conn, group_id, user_id)
    return get_group(conn, group_id, actor_id)


def remove_member(conn: sqlite3.Connection, group_id: int, actor_id: int, user_id: int) -> None:
    _require_member(conn, group_id, actor_id)
    if not repository.is_member(conn, group_id, user_id):
        raise NotFound("that user is not in this group")
    try:
        with conn:
            repository.delete_member(conn, group_id, user_id)
    except sqlite3.IntegrityError:
        # The composite foreign keys in schema.sql refuse the delete.
        raise Conflict("this member already has expenses in the group") from None


def add_expense(
    conn: sqlite3.Connection,
    group_id: int,
    actor_id: int,
    description: str,
    amount_cents: int,
    payer_id: int,
    split_type: str,
    category_id: int,
    participants: list[tuple[int, int]],
) -> dict:
    """participants is a list of (user_id, value) pairs; see splits.compute_shares."""
    _require_member(conn, group_id, actor_id)
    description = description.strip()
    if not description:
        raise InvalidInput("description must not be empty")

    if not repository.category_exists(conn, category_id):
        raise InvalidInput("unknown category")
    member_ids = set(repository.list_member_ids(conn, group_id))
    if payer_id not in member_ids:
        raise InvalidInput("the payer must be a member of the group")
    values = dict(participants)
    if len(values) != len(participants):
        raise InvalidInput("each participant may appear only once")
    if not values.keys() <= member_ids:
        raise InvalidInput("every participant must be a member of the group")

    shares = compute_shares(split_type, amount_cents, values)
    with conn:
        expense_id = repository.insert_expense(
            conn, group_id, payer_id, description, amount_cents, split_type, category_id, shares
        )
    return next(e for e in repository.list_expenses(conn, group_id) if e["id"] == expense_id)


def list_categories(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in repository.list_categories(conn)]


def spending_by_category(conn: sqlite3.Connection, group_id: int, actor_id: int) -> list[dict]:
    _require_member(conn, group_id, actor_id)
    return [dict(row) for row in repository.spending_by_category(conn, group_id)]


def list_expenses(conn: sqlite3.Connection, group_id: int, actor_id: int) -> list[dict]:
    _require_member(conn, group_id, actor_id)
    return repository.list_expenses(conn, group_id)


def delete_expense(conn: sqlite3.Connection, group_id: int, actor_id: int, expense_id: int) -> None:
    _require_member(conn, group_id, actor_id)
    with conn:
        deleted = repository.delete_expense(conn, group_id, expense_id)
    if not deleted:
        raise NotFound("expense not found")
