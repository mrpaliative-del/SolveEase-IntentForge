
from decimal import Decimal, InvalidOperation


MIN_PRICE_CENTS = 100
MAX_PRICE_CENTS = 500


def _to_cents(price: str | int | float | Decimal) -> int:
    """Convert a dollar price to integer cents safely."""
    try:
        value = Decimal(str(price).replace("$", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Price must be a valid dollar amount.")

    if not value.is_finite():
        raise ValueError("Price must be finite.")

    cents = value * 100

    if cents != cents.to_integral_value():
        raise ValueError("Price cannot contain fractions of a cent.")

    result = int(cents)

    if not MIN_PRICE_CENTS <= result <= MAX_PRICE_CENTS:
        raise ValueError("Base price must be between $1.00 and $5.00.")

    return result


def calculate_report_pricing(
    base_price: str | int | float | Decimal,
) -> dict:
    """
    Calculate report prices from taxonomy pricing.

    Returns integer cents for payment integration.
    Brief: $1.00.
    Playbook: $3.00 for base prices below $3.00;
    otherwise, use the taxonomy base price.
    """
    base_cents = _to_cents(base_price)

    brief_cents = 100
    playbook_cents = (
        300 if base_cents < 300 else base_cents
    )

    return {
        "brief_price": f"${brief_cents / 100:.2f}",
        "brief_cents": brief_cents,
        "playbook_price": f"${playbook_cents / 100:.2f}",
        "playbook_cents": playbook_cents,
    }
