#!/bin/bash

code-server --install-extension "${RIOT_WEB_VSCODE_EXTENSION_PKG}"

echo "Starting relay..."
"${RIOT_WEB_TOOL_RELAY}" &
echo "Starting code-server..."
code-server "${RIOT_WEB_CODE_SERVER_DEFAULT_WORKSPACE}"
exit 0