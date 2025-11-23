#!/bin/bash
# Docker build and run script for development
# build: docker.sh -b
# run: docker.sh -s

DEBUG=${DEBUG:-false}
BUILD=${BUILD:-false}
RUN=${RUN:-false}

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
		*)
			echo "Unknown option: $1"
			echo "Try '$0 --help' for more information."
			exit 1
			;;
	esac
done

if [[ $BUILD == true ]]; then
	echo "Building Docker Img: riot-dev-env"
	DEBUG_ARG=""
	if [[ $DEBUG == true ]]; then
		DEBUG_ARG="--progress=plain --no-cache"
	fi
	docker build ${DEBUG_ARG} -t riot-dev-env .
fi

if [[ $RUN == true ]]; then
	CONTAINER_NAME="riot-dev-con"
	
	if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
		echo "Container '${CONTAINER_NAME}' exists. Removing..."
		docker rm -f "${CONTAINER_NAME}"
	fi

	echo "Starting Docker Container: riot-dev-con"
	docker run -d --name $CONTAINER_NAME -p 80:8080 -v "./extensions:/home/coder/extensions" riot-dev-env
fi
