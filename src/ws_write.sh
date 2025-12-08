#!/bin/bash
if ! [[ -S "${RIOT_WEB_RUNTIME_WEBSOCKET_BACKSOCKET}" ]]; then
    echo "Error: WebSocket backsocket not found at ${RIOT_WEB_RUNTIME_WEBSOCKET_BACKSOCKET}"
    exit 1
fi

# echo all args into nc -> U - use unix socket, -q 0 - quit immediately after EOF on stdin
echo "$@" | nc -U -q 0 "${RIOT_WEB_RUNTIME_WEBSOCKET_BACKSOCKET}"