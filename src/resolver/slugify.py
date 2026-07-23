def slugify(name: str) -> str:
    if name is None:
        raise ValueError("slugify: name cannot be None")
    return name.lower().replace(" ", "_")
