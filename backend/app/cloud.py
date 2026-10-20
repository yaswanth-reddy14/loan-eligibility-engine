from typing import Any

from app.worker import dispatch_tick


def dispatch(event: dict[str, Any], context: Any) -> dict[str, int]:
    return {"dispatched": int(dispatch_tick())}
