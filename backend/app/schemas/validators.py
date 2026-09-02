"""Shared validators for PATCH/update schemas.

Update schemas declare required-on-the-model fields as ``T | None = None`` so
the field can be *omitted* for a partial update. That same type also lets a
client send an explicit JSON ``null``, which would try to null out a NOT NULL
database column and blow up as a 500 IntegrityError instead of a clean 422.

`reject_explicit_null` closes that gap: Pydantic only runs field validators
on values actually present in the input (not on unused defaults), so this
rejects `{"field": null}` while still allowing the field to be left out of
the payload entirely.
"""

from typing import TypeVar

T = TypeVar("T")


def reject_explicit_null(value: T | None) -> T:
    if value is None:
        raise ValueError("This field cannot be null")
    return value
