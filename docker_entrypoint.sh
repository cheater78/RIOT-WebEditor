#!/bin/bash

code-server --install-extension "${RIOT_WEB_VSCODE_EXTENSION_PKG}"

echo "Starting relay..."
"${RIOT_WEB_TOOL_RELAY}" &
echo "Starting code-server..."
code-server
exit 0