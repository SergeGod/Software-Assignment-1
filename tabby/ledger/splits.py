"""Pure functions that turn one expense into the cents each participant owes.

Every result adds up to exactly amount_cents: no cent is lost or invented.
"""

from tabby.errors import InvalidInput

SPLIT_TYPES = ("equal", "shares", "exact")


def split_by_shares(amount_cents: int, weights: dict[int, int]) -> dict[int, int]:
    """Split by weights, e.g. {alice: 2, bob: 1}. Uses the largest remainder method."""
    if amount_cents <= 0:
        raise InvalidInput("amount must be positive")
    if not weights:
        raise InvalidInput("an expense needs at least one participant")
    if any(weight <= 0 for weight in weights.values()):
        raise InvalidInput("every share must be a positive whole number")

    total_weight = sum(weights.values())
    # Round everyone down first...
    shares = {uid: amount_cents * w // total_weight for uid, w in weights.items()}
    leftover = amount_cents - sum(shares.values())
    # ...then hand the leftover cents, one each, to whoever lost the most to
    # rounding. Ties go to the lowest user id so the result is deterministic.
    by_loss = sorted(weights, key=lambda uid: (-(amount_cents * weights[uid] % total_weight), uid))
    for uid in by_loss[:leftover]:
        shares[uid] += 1
    return shares


def split_equal(amount_cents: int, user_ids: list[int]) -> dict[int, int]:
    """Equal split is a shares split where everyone has weight 1."""
    return split_by_shares(amount_cents, {uid: 1 for uid in user_ids})


def split_exact(amount_cents: int, amounts: dict[int, int]) -> dict[int, int]:
    """Each participant's amount is given; they must add up to the total."""
    if amount_cents <= 0:
        raise InvalidInput("amount must be positive")
    if not amounts:
        raise InvalidInput("an expense needs at least one participant")
    if any(cents < 0 for cents in amounts.values()):
        raise InvalidInput("exact amounts cannot be negative")
    total = sum(amounts.values())
    if total != amount_cents:
        raise InvalidInput(f"exact amounts add up to {total} cents, expected {amount_cents}")
    return dict(amounts)


def compute_shares(split_type: str, amount_cents: int, values: dict[int, int]) -> dict[int, int]:
    """values means: ignored for 'equal', weights for 'shares', cents for 'exact'."""
    if split_type == "equal":
        return split_equal(amount_cents, list(values))
    if split_type == "shares":
        return split_by_shares(amount_cents, values)
    if split_type == "exact":
        return split_exact(amount_cents, values)
    raise InvalidInput(f"split type must be one of {', '.join(SPLIT_TYPES)}")
