# RIOT WebEditor Dockerfile
# base-image: riot/riotbuild:latest
# web-editor: code-server

FROM riot/riotbuild:latest

# as created in riotbuild
ARG USERNAME="coder"
ARG USERID="1000"
ARG GROUPID="1000"

ENV DEBIAN_FRONTEND=noninteractive

# System setup
USER root
RUN apt-get update && apt-get install -y curl wget git
RUN id -u $USERNAME >/dev/null 2>&1 || \
    groupadd -g $GROUPID $USERNAME && \
    useradd -m -u $USERID -g $GROUPID -s /bin/bash $USERNAME
# code-server install
RUN curl -fsSL https://code-server.dev/install.sh | sh
# RIOT project dependencies //TODO: alr done in riotbuild?
RUN apt-get install -y make gcc-multilib python3-serial python3-psutil wget unzip git openocd gdb-multiarch esptool podman-docker clangd clang
# websocat
RUN curl -L -o /usr/local/bin/websocat https://github.com/vi/websocat/releases/download/v1.14.0/websocat.x86_64-unknown-linux-musl && chmod +x /usr/local/bin/websocat
RUN apt install -y netcat
RUN python3 -m pip install websockets

# Dev TODO: remove for dist
# Node.js and npm install for extension building
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
RUN apt-get install -y nodejs
RUN npm install -g typescript npm@latest @vscode/vsce
# Dev TODO~

# User setup
EXPOSE 8080
USER $USERNAME
ENV HOME=/home/$USERNAME
ENV SHELL=/bin/bash
WORKDIR $HOME

# RIOT Web - code-server config
ENV XDG_DATA_HOME=/home/$USERNAME/.local/share
ENV XDG_CONFIG_HOME=/home/$USERNAME/.config
COPY --chown=$USERID:$GROUPID \
    ./config/code-server.conf.yaml \
    /home/$USERNAME/.config/code-server/config.yaml
COPY --chown=$USERID:$GROUPID \
    ./config/default-vscode-user-settings.json \
    /home/$USERNAME/.local/share/code-server/User/settings.json

# RIOT Web - Runtime
#  RIOT_WEB Flag, tells RIOT that its running in the web environment
ENV RIOT_WEB=1
ENV RIOT_WEB_RUNTIME_DIRECTORY="/home/${USERNAME}/.riot-web"
RUN mkdir -p "${RIOT_WEB_RUNTIME_DIRECTORY}" && chown $USERID:$GROUPID -R "${RIOT_WEB_RUNTIME_DIRECTORY}"

# RIOT Web - Web Extension
ARG SRC_WEB_EXTENSION_SCRIPT_REINSTALL="./src/riot_web_extension_reinstall.sh"

ENV RIOT_WEB_RUNTIME_EXTENSIONS_DIRECTORY="${RIOT_WEB_RUNTIME_DIRECTORY}/extensions"
ENV RIOT_WEB_RUNTIME_RIOT_WEB_EXTENSION_DIRECTORY="${RIOT_WEB_RUNTIME_EXTENSIONS_DIRECTORY}/RIOT-WEB-FLASH-EXT-PROTOTYPE"
COPY --chown=$USERID:$GROUPID "${SRC_WEB_EXTENSION_SCRIPT_REINSTALL}" "${RIOT_WEB_RUNTIME_DIRECTORY}/riot_web_extension_reinstall.sh"

# RIOT Web - WebSocket
ARG SRC_WEBSOCKET_SCRIPT_WS_WRITE="./src/ws_write.sh"
ARG SRC_WEBSOCKET_SCRIPT_WS_RELAY="./src/ws_relay.py"

ENV RIOT_WEB_RUNTIME_WEBSOCKET_BACKSOCKET="${RIOT_WEB_RUNTIME_DIRECTORY}/ws_back.sock"
ENV RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_WRITE="${RIOT_WEB_RUNTIME_DIRECTORY}/ws_write.sh"
COPY --chown=$USERID:$GROUPID "${SRC_WEBSOCKET_SCRIPT_WS_WRITE}" "${RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_WRITE}"
ENV RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_RELAY="${RIOT_WEB_RUNTIME_DIRECTORY}/ws_relay.py"
COPY --chown=$USERID:$GROUPID "${SRC_WEBSOCKET_SCRIPT_WS_RELAY}" "${RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_RELAY}"

# RIOT Web - RIOT
ARG SRC_RIOT_PROGRAMMER_PATCH="./src/programmer.inc.mk"

ENV RIOT_WEB_RUNTIME_RIOT_DIRECTORY="${RIOT_WEB_RUNTIME_DIRECTORY}/RIOT"
ENV RIOT_DIRECTORY="/home/${USERNAME}/RIOT"
RUN git clone https://github.com/RIOT-OS/RIOT.git --recursive "${RIOT_WEB_RUNTIME_RIOT_DIRECTORY}"
#  Apply programmer patch
COPY --chown=$USERID:$GROUPID "${SRC_RIOT_PROGRAMMER_PATCH}" "${RIOT_WEB_RUNTIME_RIOT_DIRECTORY}/makefiles/tools/programmer.inc.mk"
RUN ln -s "${RIOT_WEB_RUNTIME_RIOT_DIRECTORY}" "${RIOT_DIRECTORY}"

# RIOT Web - Docker Entrypoint
ARG SRC_DOCKER_ENTRYPOINT="./src/docker_entrypoint.sh"
COPY --chown=$USERID:$GROUPID --chmod=774 "${SRC_DOCKER_ENTRYPOINT}" "${RIOT_WEB_RUNTIME_DIRECTORY}/docker_entrypoint.sh"
ENTRYPOINT []
CMD ["bash","-c","${RIOT_WEB_RUNTIME_DIRECTORY}/docker_entrypoint.sh"]