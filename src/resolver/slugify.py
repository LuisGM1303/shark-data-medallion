def slugify(name: str | None) -> str:
    if name is None:
        return ""
    return name.lower().replace(" ", "_")
