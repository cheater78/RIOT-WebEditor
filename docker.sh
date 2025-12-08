#!/bin/bash
# Docker build and run script for development
# build: docker.sh -b
# run: docker.sh -s

DEBUG=${DEBUG:-false}
UPDATE=${UPDATE:-false}
BUILD=${BUILD:-false}
RUN=${RUN:-false}

# Static config
DOCKER_IMAGE_NAME="riot-dev-env"
DOCKER_CONTAINER_NAME_BASE="riot-dev-con"

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
		-d|--debug)
			DEBUG=true
			shift
			;;
		-u|--update)
			UPDATE=true
			shift
			;;
		*)
			echo "Unknown option: $1"
			echo "Try '$0 --help' for more information."
			exit 1
			;;
	esac
done

run_silent() {
	if [[ $DEBUG != true ]]; then
		$@ > /dev/null
	else
		$@
	fi
}


if [[ $BUILD == true ]]; then
	# Build extension
	if [[ $UPDATE == true ]]; then
		run_silent git submodule update --init
	fi
	cd "${PROJECT_DIR}/extensions/RIOT-WEB-FLASH-EXT-PROTOTYPE"
	run_silent npm install
	run_silent npm run compile-web
	run_silent npm run package
	cd "${PROJECT_DIR}"

	DEBUG_ARG=""
	if [[ $DEBUG == true ]]; then
		DEBUG_ARG="--progress=plain --no-cache"
	fi
	run_silent docker build ${DEBUG_ARG} -t ${DOCKER_IMAGE_NAME} .
fi

if [[ $RUN == true ]]; then
	if [ "$(docker ps -a -q -f name=^/${DOCKER_CONTAINER_NAME_BASE}$)" ]; then
		echo "Container '${DOCKER_CONTAINER_NAME_BASE}' exists. Removing..."
		docker rm -f "${DOCKER_CONTAINER_NAME_BASE}"
	fi

	echo "Starting Docker Container: riot-dev-con"
	docker run -d --name $DOCKER_CONTAINER_NAME_BASE -p 80:8080 -p 5107:5107 -v "./extensions:/home/coder/.riot-web/extensions" "${DOCKER_IMAGE_NAME}"
fi

# reset to caller directory
cd "${PREV_DIR}"