class EnvironmentVariableExistsError(Exception): ...


class EnvironmentVariableNotExistsError(Exception): ...


class EnvironmentInitializedError(Exception): ...


class ClusterIdNotSet(Exception): ...


class ClusterSecretNotSet(Exception): ...


class WebSocketError(Exception): ...


class ServerWebSocketError(WebSocketError): ...


class ServerWebSocketUnknownDataError(ServerWebSocketError): ...


class PutQueueIgnoreError(Exception): ... 