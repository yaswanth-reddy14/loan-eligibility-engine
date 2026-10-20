from typing import Any

from app.worker import dispatch_tick


def dispatch(event: dict[str, Any], context: Any) -> dict[str, int]:
    count = 0
    for _ in range(1):
        count += int(dispatch_tick())
    return {"dispatched": count}
