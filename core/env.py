from typing import Any
from .exceptions import (
    EnvironmentVariableExistsError,
    EnvironmentVariableNotExistsError,
    EnvironmentInitializedError
)

initialized: bool = False

class Environment:
    def __init__(self) -> None:
        if initialized:
            raise EnvironmentInitializedError
        self._environments: dict[str, Any] = {}
    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._environments:
            raise EnvironmentVariableExistsError(f"'{key}' is in environments!")
        self._environments[key] = value
    def __getitem__(self, key: str) -> Any:
        if key not in self._environments:
            raise EnvironmentVariableNotExistsError(f"'{key}' is not in environments!")
        return self._environments[key]

env = Environment()