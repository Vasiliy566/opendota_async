"""Shared JSON → Pydantic parsing for async and sync clients."""

from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel


def parse_json_model(data: Any, model: type[Any] | None) -> Any:
    if model is None:
        return data
    origin = get_origin(model)
    if origin is list:
        args = get_args(model)
        inner = args[0] if args else Any
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return [inner.model_validate(x) for x in data]
        return data
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model.model_validate(data)
    return data
