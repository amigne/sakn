"""WebSocket close codes for the tool stream endpoint.

Custom close codes in the 4000-4999 range are reserved for application use
per RFC 6455 §7.4.2. Codes below 4000 are defined by the WebSocket protocol.
"""

# 4003: Reserved for "not acceptable" / forbidden — repurposed here for
# origin rejection, permission denied, and disabled-tool scenarios.
WS_CLOSE_INVALID_ORIGIN = 4003
WS_CLOSE_PERMISSION_DENIED = 4003  # tool disabled, role not allowed, or access denied
WS_CLOSE_UNKNOWN_TOOL = 4004

# 4000+ custom: semantically mapped to HTTP-like status codes for client interpretation
WS_CLOSE_RATE_LIMITED = 4029  # HTTP 429 analogue
WS_CLOSE_INVALID_SESSION = 4401  # HTTP 401 analogue (unauthenticated)
WS_CLOSE_DB_UNAVAILABLE = 4503  # HTTP 503 analogue (service unavailable — DB required for WS auth)
