from __future__ import annotations

def is_constraint_violation(
    exception: BaseException,
    constraint_name: str,
) -> bool:
    current: BaseException | None = exception
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if getattr(current, "constraint_name", None) == constraint_name:
            return True

        diag = getattr(current, "diag", None)
        if getattr(diag, "constraint_name", None) == constraint_name:
            return True

        if constraint_name in str(current):
            return True

        current = (
            getattr(current, "__cause__", None)
            or getattr(current, "__context__", None)
        )

    return False
