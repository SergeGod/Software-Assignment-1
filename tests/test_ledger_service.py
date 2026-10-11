import pytest

from tabby.errors import Conflict, Forbidden, InvalidInput, NotFound
from tabby.ledger import interface, service

GROCERIES, RENT = 1, 2


@pytest.fixture
def group(conn, users):
    """'Flat' with alice, bob and carol."""
    created = service.create_group(conn, users["alice"], "Flat", [users["bob"], users["carol"]])
    return created["id"]


def add(conn, group_id, actor, payer, amount, split_type="equal", participants=None, category=GROCERIES):
    return service.add_expense(
        conn, group_id, actor, "Shopping", amount, payer, split_type, category, participants
    )


def test_create_group_adds_creator_and_friends(conn, users, group):
    detail = service.get_group(conn, group, users["bob"])
    assert detail["name"] == "Flat"
    assert [m["username"] for m in detail["members"]] == ["alice", "bob", "carol"]
    assert [g["id"] for g in service.list_groups(conn, users["carol"])] == [group]
    assert service.list_groups(conn, users["dave"]) == []


def test_create_group_rejects_non_friends_and_empty_name(conn, users):
    with pytest.raises(InvalidInput):
        service.create_group(conn, users["alice"], "Flat", [users["dave"]])
    with pytest.raises(InvalidInput):
        service.create_group(conn, users["alice"], "   ", [])


def test_only_members_can_see_a_group(conn, users, group):
    with pytest.raises(Forbidden):
        service.get_group(conn, group, users["dave"])
    with pytest.raises(NotFound):
        service.get_group(conn, 999, users["alice"])


def test_add_member_must_be_a_friend_and_not_already_in(conn, users):
    group_id = service.create_group(conn, users["alice"], "Trip", [])["id"]
    with pytest.raises(InvalidInput):
        service.add_member(conn, group_id, users["alice"], users["dave"])
    service.add_member(conn, group_id, users["alice"], users["bob"])
    with pytest.raises(Conflict):
        service.add_member(conn, group_id, users["alice"], users["bob"])


def test_add_expense_stores_shares_that_add_up(conn, users, group):
    ids = [users["alice"], users["bob"], users["carol"]]
    expense = add(conn, group, users["alice"], users["alice"], 1000, "equal", [(u, 1) for u in ids])
    assert expense["shares"] == {ids[0]: 334, ids[1]: 333, ids[2]: 333}
    assert expense["category_id"] == GROCERIES
    assert service.list_expenses(conn, group, users["bob"])[0]["id"] == expense["id"]


@pytest.mark.parametrize("problem", ["payer", "participant", "duplicate", "category", "description"])
def test_add_expense_rejects_invalid_input(conn, users, group, problem):
    alice, bob, dave = users["alice"], users["bob"], users["dave"]
    payer, participants, category, description = alice, [(alice, 1), (bob, 1)], GROCERIES, "Shop"
    if problem == "payer":
        payer = dave
    elif problem == "participant":
        participants = [(alice, 1), (dave, 1)]
    elif problem == "duplicate":
        participants = [(alice, 1), (alice, 1)]
    elif problem == "category":
        category = 999
    else:
        description = "  "
    with pytest.raises(InvalidInput):
        service.add_expense(
            conn, group, alice, description, 1000, payer, "equal", category, participants
        )


def test_non_member_cannot_add_expense(conn, users, group):
    with pytest.raises(Forbidden):
        add(conn, group, users["dave"], users["alice"], 100, "equal", [(users["alice"], 1)])


def test_member_with_expenses_cannot_be_removed_until_they_are_deleted(conn, users, group):
    alice, carol = users["alice"], users["carol"]
    expense = add(conn, group, alice, alice, 600, "equal", [(alice, 1), (carol, 1)])
    with pytest.raises(Conflict):
        service.remove_member(conn, group, alice, carol)

    service.delete_expense(conn, group, alice, expense["id"])
    service.remove_member(conn, group, alice, carol)
    assert not interface.is_member(conn, group, carol)


def test_remove_member_that_is_not_in_group(conn, users, group):
    with pytest.raises(NotFound):
        service.remove_member(conn, group, users["alice"], users["dave"])


def test_delete_missing_expense(conn, users, group):
    with pytest.raises(NotFound):
        service.delete_expense(conn, group, users["alice"], 999)


def test_spending_by_category(conn, users, group):
    alice, bob = users["alice"], users["bob"]
    add(conn, group, alice, alice, 4500, participants=[(alice, 1), (bob, 1)])
    add(conn, group, bob, bob, 1500, participants=[(alice, 1), (bob, 1)])
    add(conn, group, alice, alice, 120000, participants=[(alice, 1), (bob, 1)], category=RENT)
    assert service.spending_by_category(conn, group, bob) == [
        {"category_id": RENT, "name": "Rent", "total_cents": 120000},
        {"category_id": GROCERIES, "name": "Groceries", "total_cents": 6000},
    ]
    assert len(service.list_categories(conn)) == 9


def test_get_group_ledger_is_plain_data_for_settlement(conn, users, group):
    alice, bob = users["alice"], users["bob"]
    add(conn, group, alice, bob, 3000, "exact", [(alice, 1000), (bob, 2000)])
    ledger = interface.get_group_ledger(conn, group)
    assert ledger.member_ids == [alice, bob, users["carol"]]
    assert len(ledger.expenses) == 1
    assert ledger.expenses[0].payer_id == bob
    assert ledger.expenses[0].shares == {alice: 1000, bob: 2000}
    assert interface.get_group_ledger(conn, 999) is None
