class ClusterIdNotSet(Exception):
    pass


class ClusterSecretNotSet(Exception):
    pass


class WebSocketError(Exception): 
    pass


class ServerWebSocketError(WebSocketError): 
    pass


class ServerWebSocketUnknownDataError(ServerWebSocketError): 
    pass