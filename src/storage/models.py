from dataclasses import dataclass, field

@dataclass(frozen=True)
class Detection:
    matched_terms: tuple[str, ...]
    products: tuple[str, ...]
    evidence: tuple[str, ...]
    relationship_terms: tuple[str, ...] = field(default_factory=tuple)

