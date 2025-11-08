# RIOT WebEditor Dockerfile
# base-image: riot/riotbuild:latest
# web-editor: code-server

FROM riot/riotbuild:latest

# as created in riotbuild
ARG USERNAME="coder"
ARG USERID="1000"
ARG GROUPID="1000"

ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash

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

# Dev TODO: remove for dist
# Node.js and npm install for extension building
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs
# Dev TODO~

# User setup
EXPOSE 8080
USER $USERNAME
ENV HOME=/home/$USERNAME
ENV XDG_DATA_HOME=$HOME/.local/share
ENV XDG_CONFIG_HOME=$HOME/.config
WORKDIR $HOME

COPY --chown=$USERID:$GROUPID \
    ./config/code-server.conf.yaml \
    /home/$USERNAME/.config/code-server/config.yaml
COPY --chown=$USERID:$GROUPID \
    ./config/default-vscode-user-settings.json \
    /home/$USERNAME/.local/share/code-server/User/settings.json
COPY --chown=$USERID:$GROUPID \
    ./extensions \
    /home/$USERNAME/.local/share/code-server/extensions

# Dev TODO: remove for dist ()
RUN cd /home/$USERNAME/.local/share/code-server/extensions/RIOT-WEB-FLASH-EXT-PROTOTYPE && \
    npm install && npm run compile-web
# Dev TODO~

RUN git clone https://github.com/cheater78/RIOT-WEB.git --recursive /home/$USERNAME/RIOT

# Container startup command
CMD ["code-server"]