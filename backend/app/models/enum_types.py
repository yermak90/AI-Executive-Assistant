import enum

from sqlalchemy import Enum as SqlEnum


def portable_enum(enum_cls: type[enum.Enum], name: str, length: int = 32) -> SqlEnum:
    """A string-backed enum column (VARCHAR + CHECK constraint) instead of a
    native PostgreSQL ENUM type. Native PG enums require ALTER TYPE ... ADD
    VALUE to extend and cannot drop values or be cleanly reversed by a plain
    DROP TYPE during `alembic downgrade` once other objects depend on them.
    A portable enum keeps upgrade/downgrade/upgrade cycles simple and lets
    new enum members be added with an ordinary column-level migration."""
    return SqlEnum(
        enum_cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        length=length,
    )
