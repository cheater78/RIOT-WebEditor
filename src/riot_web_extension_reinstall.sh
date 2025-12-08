#!/bin/bash

# uninstall the extension
code-server --uninstall-extension "${RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_PACKAGE}"

# remove the old cached extension folder

# install the new extension
[[ -f "${RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_PACKAGE}" ]] && code-server --install-extension "${RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_PACKAGE}"
