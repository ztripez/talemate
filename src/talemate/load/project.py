"""Project identity helpers used while loading scenes."""


def to_project_name(name: str) -> str:
    """Normalize a scene display name for its conventional project directory.

    Args:
        name: Scene display name to normalize.

    Returns:
        A lowercase name with spaces replaced by hyphens and apostrophes removed.

    Invariants:
        Characters other than spaces, apostrophes, and letter case are preserved.

    """
    return name.replace(" ", "-").replace("'", "").lower()
