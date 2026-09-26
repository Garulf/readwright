"""Render GitHub READMEs from Jinja2 templates."""


def __getattr__(name: str) -> str:
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("readwright")
    except PackageNotFoundError:
        return "0.0.0"
