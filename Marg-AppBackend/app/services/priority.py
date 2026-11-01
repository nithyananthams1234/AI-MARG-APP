
from decimal import Decimal, ROUND_HALF_UP


PRIORITY_WEIGHTS = {
    "urgency": Decimal("0.30"),
    "impact": Decimal("0.25"),
    "risk": Decimal("0.20"),
    "deadline_proximity": Decimal("0.15"),
    "workload_dependency": Decimal("0.10"),
}


def calculate_priority_score(
    urgency: int,
    impact: int,
    risk: int,
    deadline_proximity: int,
    workload_dependency: int,
) -> int:
    """Calculate the weighted priority score from 0 to 100."""

    factors = {
        "urgency": urgency,
        "impact": impact,
        "risk": risk,
        "deadline_proximity": deadline_proximity,
        "workload_dependency": workload_dependency,
    }

    for name, value in factors.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer.")

        if not 0 <= value <= 100:
            raise ValueError(f"{name} must be between 0 and 100.")

    score = sum(
        Decimal(factors[name]) * weight
        for name, weight in PRIORITY_WEIGHTS.items()
    )

    return int(score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_priority_level(score: int) -> str:
    """Convert a priority score into its official priority level."""

    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError("Priority score must be an integer.")

    if not 0 <= score <= 100:
        raise ValueError("Priority score must be between 0 and 100.")

    if score >= 75:
        return "critical"
    elif score >= 50:
        return "high"
    elif score >= 25:
        return "medium"

    return "low"


def calculate_task_priority(
    urgency: int,
    impact: int,
    risk: int,
    deadline_proximity: int,
    workload_dependency: int,
) -> dict:
    """Return the calculated score and priority level."""

    score = calculate_priority_score(
        urgency=urgency,
        impact=impact,
        risk=risk,
        deadline_proximity=deadline_proximity,
        workload_dependency=workload_dependency,
    )

    return {
        "priority_score": score,
        "priority": get_priority_level(score),
    }
