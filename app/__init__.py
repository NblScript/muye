from __future__ import annotations

__all__ = ["MuyeApplication", "api_app", "parse_args"]


def __getattr__(name: str):
    """Lazy import to avoid RuntimeWarning with ``python -m app.main``."""
    if name in __all__:
        from app.main import MuyeApplication, api_app, parse_args

        globals().update(
            MuyeApplication=MuyeApplication,
            api_app=api_app,
            parse_args=parse_args,
        )
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
