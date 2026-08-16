def added_removed(previous: tuple[str,...], current: tuple[str,...]) -> tuple[set[str],set[str]]:
    return set(current)-set(previous),set(previous)-set(current)

