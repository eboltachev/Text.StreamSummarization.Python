"""Shared helpers for schema modules.

The project typically depends on Pydantic for schema definitions. Because the
execution environment used in the automated tests does not provide the real
``pydantic`` package, we expose a tiny ``BaseModel`` fallback that mimics the
minimal behaviour the service relies on.  Concrete schema modules import
``BaseModel`` from here so they remain agnostic to whether the real dependency
is available.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict

try:  # pragma: no cover - executed when pydantic is installed
    from pydantic import BaseModel as _BaseModel
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained envs

    class _BaseModel:
        """Very small substitute that emulates attribute access semantics.

        The implementation focuses on the behaviours our tests require:

        * instantiation using keyword arguments;
        * attribute access via ``obj.field``;
        * converting back to ``dict`` using ``dict()`` or ``model_dump``.

        Any nested dataclasses are converted to dictionaries when dumping so
        the rest of the service can keep operating on built-in structures.
        """

        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

        def dict(self) -> Dict[str, Any]:
            return {
                key: self._convert(getattr(self, key))
                for key in self.__dict__.keys()
            }

        model_dump = dict

        def model_copy(self, *, update: Dict[str, Any] | None = None) -> "_BaseModel":
            data = self.dict()
            if update:
                data.update(update)
            return self.__class__(**data)

        @staticmethod
        def _convert(value: Any) -> Any:
            if isinstance(value, _BaseModel):
                return value.dict()
            if is_dataclass(value):
                return asdict(value)
            if isinstance(value, list):
                return [_BaseModel._convert(item) for item in value]
            if isinstance(value, dict):
                return {
                    key: _BaseModel._convert(item)
                    for key, item in value.items()
                }
            return value


BaseModel = _BaseModel

__all__ = ["analysis", "session", "user", "BaseModel"]
