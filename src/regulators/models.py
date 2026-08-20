from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegulatoryRecord:
    regulator_id: str
    legal_name: str
    license_number: str
    normalized_status: str
    source_status: str
    source_url: str
    company_number: str | None = None
    country: str | None = None
    license_type: str | None = None
    license_date: str | None = None
    termination_date: str | None = None
    domains: tuple[str, ...] = field(default_factory=tuple)
