class ClusterIdNotSet(Exception):
    ...


class ClusterSecretNotSet(Exception):
    ...


class WebSocketError(Exception): 
    ...


class ServerWebSocketError(WebSocketError): 
    ...


class ServerWebSocketUnknownDataError(ServerWebSocketError): 
    ...