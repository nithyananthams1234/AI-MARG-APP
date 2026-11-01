"""Principal and permission checks.

PROVISIONAL: MARG authentication and role names are not yet known (pending the MARG OpenAPI
compatibility audit). In development, the caller identifies itself with the ``X-Actor-Ref`` and
``X-Actor-Role`` headers. Supervisor-like roles are configured through ``DEV_SUPERVISOR_ROLES``.
No final MARG roles are defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PrincipalKind(StrEnum):
    human = "human"
    system = "system"


@dataclass(frozen=True)
class Principal:
    actor_ref: str
    roles: frozenset[str] = field(default_factory=frozenset)
    kind: PrincipalKind = PrincipalKind.human


class PermissionDenied(Exception):
    """The principal may not perform the requested operation."""


def can_access_mentor(principal: Principal, mentor_ref: str, supervisor_roles: set[str]) -> bool:
    if principal.kind is PrincipalKind.system:
        return True
    return principal.actor_ref == mentor_ref or bool(principal.roles & supervisor_roles)


def ensure_mentor_access(principal: Principal, mentor_ref: str, supervisor_roles: set[str]) -> None:
    if not can_access_mentor(principal, mentor_ref, supervisor_roles):
        raise PermissionDenied("Not permitted to access another mentor's data")


def ensure_can_approve(principal: Principal, mentor_ref: str, supervisor_roles: set[str]) -> None:
    """Approvals must come from a human: the owning mentor or a configured supervisor role."""
    if principal.kind is not PrincipalKind.human:
        raise PermissionDenied("Only a human principal can approve or reject proposals")
    if not (principal.actor_ref == mentor_ref or principal.roles & supervisor_roles):
        raise PermissionDenied("Only the owning mentor or an authorised supervisor can decide this proposal")
