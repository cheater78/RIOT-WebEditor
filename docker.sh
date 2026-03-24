#!/bin/bash
# Docker build and run script for development
# build: docker.sh -b
# run: docker.sh -s

DEBUG=${DEBUG:-false}
UPDATE=${UPDATE:-false}
BUILD=${BUILD:-false}
RUN=${RUN:-false}
SKIP_NPM=${SKIP_NPM:-false}
VERBOSE=${VERBOSE:-false}

# Static config
DOCKER_IMAGE_NAME="riot-dev-env"
DOCKER_CONTAINER_NAME_BASE="riot-dev-con"

RIOT_VSCODE_EXTENSION_BRANCH="master"

# project root
PREV_DIR=$(pwd)
PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "${PROJECT_DIR}"

while [[ $# -gt 0 ]]; do
	case "$1" in
		-b|--build)
			BUILD=true
			shift
			;;
		-s|--start)
			RUN=true
			shift
			;;
		-u|--update)
			UPDATE=true
			shift
			;;
		-n|--no-pkg-build)
			SKIP_NPM=true
			shift
			;;
		-v|--verbose)
			VERBOSE=true
			shift
			;;
		-d|--debug)
			DEBUG=true
			VERBOSE=true
			shift
			;;
		*)
			echo "Unknown option: $1"
			exit 1
			;;
	esac
done

run_silent() {
	if [[ $VERBOSE != true ]]; then
		$@ > /dev/null
	else
		$@
	fi
}

if [[ $UPDATE == true ]]; then
	cd "${PROJECT_DIR}/extensions/RIOT-VS-Code-Extension/extensions/web"
	run_silent git stash
	run_silent git checkout $RIOT_VSCODE_EXTENSION_BRANCH
	run_silent git pull
	cd "${PROJECT_DIR}"
fi

if [[ $BUILD == true ]]; then
	if [[ $SKIP_NPM == false ]]; then
		cd "${PROJECT_DIR}/extensions/RIOT-VS-Code-Extension/extensions/web"
		run_silent npm install
		run_silent npm run compile-web
		run_silent npm run package
		cd "${PROJECT_DIR}"
	fi

	run_silent "${PROJECT_DIR}/riot-web-tools/ship.sh"

	DEBUG_ARG=""
	if [[ $DEBUG == true ]]; then
		DEBUG_ARG="--progress=plain --no-cache"
	fi
	run_silent docker build ${DEBUG_ARG} -t ${DOCKER_IMAGE_NAME} .
fi

if [[ $RUN == true ]]; then
	if [ "$(docker ps -a -q -f name=^/${DOCKER_CONTAINER_NAME_BASE}$)" ]; then
		echo "Container '${DOCKER_CONTAINER_NAME_BASE}' exists. Removing..."
		run_silent docker rm -f "${DOCKER_CONTAINER_NAME_BASE}"
	fi

	echo "Starting Docker Container: riot-dev-con"
	run_silent docker run -d --name $DOCKER_CONTAINER_NAME_BASE -p 80:8080 -p 7777:7777 "${DOCKER_IMAGE_NAME}"
fi

# reset to caller directory
cd "${PREV_DIR}"