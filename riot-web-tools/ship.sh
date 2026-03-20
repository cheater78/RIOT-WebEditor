#!/bin/bash
SCRIPTPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRCPATH="${SCRIPTPATH}/src/riot_web_tools"
DISTPATH="${SCRIPTPATH}/dist"
BUILDPATH="${SCRIPTPATH}/build"

build() {
    script=$1

    # keep .spec, but in build
    cd "${BUILDPATH}"

    python3 -m PyInstaller \
        --onedir \
        --noconfirm \
        --name $script \
        --distpath "${DISTPATH}" \
        --workpath "${BUILDPATH}" \
        "${SRCPATH}/${script}.py"

    # alternatively remove thema
    # rm "${script}.spec"
}

build relay
build stub
build shell