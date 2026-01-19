#!/bin/bash

# uninstall the extension
code-server --uninstall-extension barkolores78.riot-web-extension

cd "$RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_DIRECTORY"
npm install
npm run compile-web
npm run package
cd ~

package_files=($RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_DIRECTORY/riot-web-extension-*)

if (( ${#package_files[@]} < 1 )); then
    echo "No package found!"
    exit 1
fi

if (( ${#package_files[@]} > 1 )); then
    echo "${#package_files[@]} packages found!"
    echo "${package_files[@]}"
    echo "Using: ${package_files[0]}"
fi

# install the new extension
echo "Installing extension: ${package_files[0]}"
code-server --install-extension "${package_files[0]}"
