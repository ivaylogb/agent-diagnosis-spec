"""Schema validators for the Finding and StructuredEdit objects.

``finding.schema.json`` ``$ref``s ``structured-edit.schema.json`` by its
absolute ``$id``; both are registered in a ``referencing`` registry so the
cross-reference resolves without network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import best_match
from referencing import Registry, Resource

from .schemas import (
    FINDING_SCHEMA_ID,
    STRUCTURED_EDIT_SCHEMA_ID,
    load_finding_schema,
    load_structured_edit_schema,
    schema_store,
)


@dataclass
class ValidationResult:
    """Outcome of validating one object against a normative schema."""

    valid: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # convenience: `if result:`
        return self.valid


def _registry() -> Registry:
    return Registry().with_resources(
        [
            (sid, Resource.from_contents(schema))
            for sid, schema in schema_store().items()
        ]
    )


def _format_error(err: Any) -> str:
    """Render one error, descending into oneOf/anyOf context for specificity.

    A bare oneOf failure ("is not valid under any of the given schemas") is
    not actionable; the concrete sub-error ("'line_end' is a required
    property") is. We follow `context` to the best-matching branch.
    """
    if err.context:
        sub = best_match(err.context)
        if sub is not None:
            return _format_error(sub)
    location = "/".join(str(p) for p in err.absolute_path)
    where = f" at /{location}" if location else ""
    return f"{err.message}{where}"


def _validate(instance: Any, schema: dict[str, Any]) -> ValidationResult:
    validator = Draft7Validator(schema, registry=_registry())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return ValidationResult(valid=True, errors=[])
    return ValidationResult(valid=False, errors=[_format_error(e) for e in errors])


def validate_finding(finding_dict: dict[str, Any]) -> ValidationResult:
    """Validate one Finding object against ``finding.schema.json``."""
    return _validate(finding_dict, load_finding_schema())


def validate_structured_edit(edit_dict: dict[str, Any]) -> ValidationResult:
    """Validate one structured edit against ``structured-edit.schema.json``."""
    return _validate(edit_dict, load_structured_edit_schema())


__all__ = [
    "ValidationResult",
    "validate_finding",
    "validate_structured_edit",
    "FINDING_SCHEMA_ID",
    "STRUCTURED_EDIT_SCHEMA_ID",
]
