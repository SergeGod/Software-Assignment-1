import pytest

from tabby.errors import InvalidInput
from tabby.ledger.splits import compute_shares, split_by_shares, split_equal, split_exact


def test_equal_split_gives_leftover_cent_to_lowest_id():
    assert split_equal(1000, [1, 2, 3]) == {1: 334, 2: 333, 3: 333}


def test_equal_split_without_remainder():
    assert split_equal(900, [1, 2, 3]) == {1: 300, 2: 300, 3: 300}


def test_shares_split_gives_leftover_to_biggest_rounding_loss():
    # 1001 * 2/4 = 500.5 loses the most to rounding, so alice gets the extra cent.
    assert split_by_shares(1001, {1: 2, 2: 1, 3: 1}) == {1: 501, 2: 250, 3: 250}


def test_shares_tie_break_is_by_user_id_not_input_order():
    assert split_by_shares(101, {5: 1, 2: 1}) == {2: 51, 5: 50}


@pytest.mark.parametrize("amount", range(1, 300))
def test_shares_always_add_up_to_amount(amount):
    shares = split_by_shares(amount, {1: 3, 2: 5, 3: 7, 4: 1})
    assert sum(shares.values()) == amount
    assert all(cents >= 0 for cents in shares.values())


@pytest.mark.parametrize(
    "amount, weights",
    [(0, {1: 1}), (-5, {1: 1}), (100, {}), (100, {1: 1, 2: 0}), (100, {1: -1})],
)
def test_shares_rejects_bad_input(amount, weights):
    with pytest.raises(InvalidInput):
        split_by_shares(amount, weights)


def test_exact_split_accepts_amounts_that_add_up():
    assert split_exact(5000, {1: 3000, 2: 2000}) == {1: 3000, 2: 2000}


@pytest.mark.parametrize(
    "amount, amounts",
    [(5000, {1: 2000, 2: 2000}), (5000, {1: 6000, 2: -1000}), (0, {1: 0}), (100, {})],
)
def test_exact_split_rejects_bad_input(amount, amounts):
    with pytest.raises(InvalidInput):
        split_exact(amount, amounts)


def test_compute_shares_dispatches_on_split_type():
    assert compute_shares("equal", 100, {1: 99, 2: 0}) == {1: 50, 2: 50}  # values ignored
    assert compute_shares("shares", 300, {1: 2, 2: 1}) == {1: 200, 2: 100}
    assert compute_shares("exact", 300, {1: 100, 2: 200}) == {1: 100, 2: 200}


def test_compute_shares_rejects_unknown_type():
    with pytest.raises(InvalidInput):
        compute_shares("random", 100, {1: 1})
