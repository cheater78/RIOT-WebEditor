# RIOT WebEditor Dockerfile

FROM debian:bookworm-slim@sha256:98f4b71de414932439ac6ac690d7060df1f27161073c5036a7553723881bffbe

ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL="C.UTF-8"
ENV LANG="C.UTF-8"

# System setup
USER root
# create USER
ARG USERNAME="coder"
ARG USERID="1000"
ARG GROUPID="1000"
ARG SHELL="/bin/bash"

# RIOT User environment
RUN id -u $USERNAME >/dev/null 2>&1 || \
    groupadd -g $GROUPID $USERNAME && \
    useradd -m -u $USERID -g $GROUPID -s $SHELL $USERNAME
ENV SHELL=$SHELL

# RIOT dependencies
ARG LLVM_VERSION=14
RUN \
    dpkg --add-architecture i386 >&2 && \
    echo 'Update the package index files to latest available versions' >&2 && \
    apt-get update \
    && echo 'Installing native toolchain and build system functionality' >&2 && \
    apt-get -y --no-install-recommends install \
        afl++ \
        automake \
        bsdmainutils \
        build-essential \
        ca-certificates \
        ccache \
        cmake \
        curl \
        cython3 \
        gcc \
        gcc-multilib \
        gdb \
        git \
        g++-multilib \
        libffi-dev \
        libpcre3 \
        libtool \
        libsdl2-dev \
        libsdl2-dev:i386 \
        m4 \
        ninja-build \
        parallel \
        protobuf-compiler \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-venv \
        python3-wheel \
        python3-full \
        p7zip \
        qemu-system-arm \
        rsync \
        socat \
        ssh-client \
        subversion \
        unzip \
        vim-common \
        wget \
        xsltproc \
    && echo 'Installing LLVM/Clang toolchain' >&2 && \
    apt-get -y --no-install-recommends install \
        llvm-${LLVM_VERSION} \
        clang-${LLVM_VERSION} \
        clang-tools-${LLVM_VERSION} \
        lld-${LLVM_VERSION} \
        llvm \
        clang \
        clang-tools \
    && echo 'Installing C2Rust (build) dependencies' >&2 && \
    apt-get -y --no-install-recommends install \
        libclang-dev \
        libssl-dev \
        llvm-dev \
        && \
    SYMS=$(find /usr/bin -type l) && \
    for file in ${SYMS}; do \
        SYMTARGET=$(readlink -f ${file}) && \
        SYMNAME=${file%"-${LLVM_VERSION}"} && \
        # Filter by symlinks starting with /usr/bin/llvm-${LLVM_VERSION}
        case "${SYMTARGET}" in "/usr/lib/llvm-${LLVM_VERSION}"* ) ln -sf ${SYMTARGET} ${SYMNAME}; esac \
    done \
    && echo 'Installing additional packages required for ESP32 toolchain' >&2 && \
    apt-get -y --no-install-recommends install \
        python3-serial \
        telnet
# Removed MP430

# Removed ARM

# Removed MIPS

# Removed RISC-V binary toolchain

# Install complete ESP8266 toolchain in /opt/esp (139 MB after cleanup)
# remember https://github.com/RIOT-OS/RIOT/pull/10801 when updating
RUN echo 'Installing ESP8266 toolchain' >&2 && \
    mkdir -p /opt/esp && \
    cd /opt/esp && \
    git clone https://github.com/gschorcht/xtensa-esp8266-elf && \
    cd xtensa-esp8266-elf && \
    git checkout -q 696257c2b43e2a107d3108b2c1ca6d5df3fb1a6f && \
    rm -rf .git && \
    cd /opt/esp && \
    git clone https://github.com/gschorcht/RIOT-Xtensa-ESP8266-RTOS-SDK.git ESP8266_RTOS_SDK && \
    cd ESP8266_RTOS_SDK/ && \
    git checkout -q c0174eff7278eb5beea66ce1f65b7af57432d2a9 && \
    rm -rf .git* docs examples Kconfig make README.md tools && \
    cd components && \
    rm -rf app_update aws_iot bootloader cjson coap espos esptool_py esp-tls \
           freertos jsmn libsodium log mdns mqtt newlib partition_table \
           pthread smartconfig_ack spiffs ssl tcpip_adapter vfs && \
    find . -type f -name '*.[csS]' -exec rm {} \; && \
    find . -type f -name '*.cpp' -exec rm {} \;

ENV PATH="${PATH}:/opt/esp/xtensa-esp8266-elf/bin"
ENV ESP8266_RTOS_SDK_DIR="/opt/esp/ESP8266_RTOS_SDK"

# Install ESP32x Xtensa toolchain in /opt/esp (1.1 GB)
ARG ESP32_GCC_RELEASE="esp-14.2.0_20241119"
ARG ESP32_GCC_VERSION_DIR="14.2.0"
ARG ESP32_GCC_VERSION_DOWNLOAD="14.2.0_20241119"
ARG ESP32_GCC_REPO=https://github.com/espressif/crosstool-NG/releases/download

ARG ESP32_GCC_FILE=xtensa-esp-elf-${ESP32_GCC_VERSION_DOWNLOAD}-x86_64-linux-gnu.tar.xz
ARG ESP32_GCC_URL=${ESP32_GCC_REPO}/${ESP32_GCC_RELEASE}/${ESP32_GCC_FILE}

RUN echo 'Installing ESP32 toolchain for Xtensa' >&2 && \
    curl -L ${ESP32_GCC_URL} | tar -C /opt/esp -xJ
ENV PATH="${PATH}:/opt/esp/xtensa-esp-elf/bin"

# Install ESP32x RISC-V toolchain in /opt/esp (2.1 GB)
ARG ESP32_GCC_FILE=riscv32-esp-elf-${ESP32_GCC_VERSION_DOWNLOAD}-x86_64-linux-gnu.tar.xz
ARG ESP32_GCC_URL=${ESP32_GCC_REPO}/${ESP32_GCC_RELEASE}/${ESP32_GCC_FILE}

RUN echo 'Installing ESP32 toolchain for RISC-V' >&2 && \
    curl -L ${ESP32_GCC_URL} | tar -C /opt/esp -xJ
ENV PATH="${PATH}:/opt/esp/riscv32-esp-elf/bin"

# Removed ESP GDB

# Removed PICOLIB (Rust)

# RIOT toolchains
ARG RIOT_TOOLCHAIN_GCC_VERSION=10.1.0
ARG RIOT_TOOLCHAIN_PACKAGE_VERSION=18
ARG RIOT_TOOLCHAIN_TAG=20200722112854-64162e7
ARG RIOT_TOOLCHAIN_GCCPKGVER=${RIOT_TOOLCHAIN_GCC_VERSION}-${RIOT_TOOLCHAIN_PACKAGE_VERSION}
ARG RIOT_TOOLCHAIN_SUBDIR=${RIOT_TOOLCHAIN_GCCPKGVER}-${RIOT_TOOLCHAIN_TAG}

# Removed MSP430 toolchain

# install required python packages from file
# numpy must be already installed before installing some other requirements (emlearn)
#RUN apt install -y --no-install-recommends python3-numpy
#COPY requirements.txt /tmp/requirements.txt
#RUN echo 'Installing python3 packages' >&2 \
#    && apt -y --no-install-recommends install python3-pybind11 \
#    && pip3 install --no-cache-dir -r /tmp/requirements.txt \
#    && rm /tmp/requirements.txt

# Removed Rust build toolchain

# get laze binary
# TODO: doesnt work -> /tmp/requirements.txt missing
# COPY --from=kaspar030/laze:sha-caf7e5b-bookworm@sha256:50865615635532f7ee38dacc612f85157c75b0019165bb87d0ff440e06ebe838 /laze /usr/bin/laze

# get Dockerfile version from build args
ARG RIOTBUILD_VERSION="unknown"
ENV RIOTBUILD_VERSION="${RIOTBUILD_VERSION}"

ARG RIOTBUILD_COMMIT="unknown"
ENV RIOTBUILD_COMMIT="${RIOTBUILD_COMMIT}"

ARG RIOTBUILD_BRANCH="unknown"
ENV RIOTBUILD_BRANCH="${RIOTBUILD_BRANCH}"

# watch for single ">" vs double ">>"!
RUN echo "RIOTBUILD_VERSION=$RIOTBUILD_VERSION" > /etc/riotbuild
RUN echo "RIOTBUILD_COMMIT=$RIOTBUILD_COMMIT" >> /etc/riotbuild
RUN echo "RIOTBUILD_BRANCH=$RIOTBUILD_BRANCH" >> /etc/riotbuild

# RIOT project dependencies //TODO: alr done in riotbuild?
# RUN apt-get install -y make gcc-multilib python3-serial python3-psutil wget unzip git openocd gdb-multiarch esptool podman-docker clangd clang

# RIOT-WEB
ENV RIOT_WEB_USER_HOME="/home/${USERNAME}"
ENV RIOT_WEB_CONF="${RIOT_WEB_USER_HOME}/.riot-web"
ENV RIOT_WEB_TOOLS="/usr/bin/riot-web"

RUN echo "Creating user home directory" \
    && mkdir -m 777 -p "${RIOT_WEB_USER_HOME}" \
    && chown $USERID:$GROUPID -R "${RIOT_WEB_USER_HOME}"

RUN echo "Creating riot web user config directory" \
    && mkdir -m 777 -p "${RIOT_WEB_CONF}" \
    && chown $USERID:$GROUPID -R "${RIOT_WEB_CONF}"

RUN echo "Creating riot web tool directory" \
    && mkdir -m 777 -p "${RIOT_WEB_TOOLS}" \
    && chown root:root -R "${RIOT_WEB_TOOLS}"

# riot web tool(s)
RUN apt install -y \
    python3-cbor2 \
    python3-websockets

ARG RIOT_WEB_TOOL_SRC="./src"

ENV RIOT_WEB_TOOL_RELAY="${RIOT_WEB_TOOLS}/relay.py"
ENV RIOT_WEB_TOOL_STUB="${RIOT_WEB_TOOLS}/stub.py"
ENV RIOT_WEB_TOOL_SHELL="${RIOT_WEB_TOOLS}/shell.py"

COPY "${RIOT_WEB_TOOL_SRC}" "${RIOT_WEB_TOOLS}"

# riot web - riot preinstall
ENV RIOT_WEB_RIOT_DIR="${RIOT_WEB_USER_HOME}/RIOT"
RUN echo "Installing RIOT" \
    && git clone https://github.com/RIOT-OS/RIOT.git --recursive "${RIOT_WEB_RIOT_DIR}"

# riot web - riot patch
ARG RIOT_WEB_RIOT_PATCH_PROGRAMMER_SRC="./riot-patch/programmer.inc.mk"
ARG RIOT_WEB_RIOT_PATCH_SERIAL_SRC="./riot-patch/serial.inc.mk"

COPY --chown=$USERID:$GROUPID "${RIOT_WEB_RIOT_PATCH_PROGRAMMER_SRC}" "${RIOT_WEB_RIOT_DIR}/makefiles/tools/programmer.inc.mk"
COPY --chown=$USERID:$GROUPID "${RIOT_WEB_RIOT_PATCH_SERIAL_SRC}" "${RIOT_WEB_RIOT_DIR}/makefiles/tools/serial.inc.mk"

# coder/code-server
# CODE-SERVER has a associated VSCODE version, needs to be set in the extensions, package.json -> engines: vscode correctly!!
ARG RIOT_WEB_CODE_SERVER_VERSION="4.109.2"
ARG RIOT_WEB_CODE_SERVER_PKG="code-server_${RIOT_WEB_CODE_SERVER_VERSION}_amd64.deb"
ARG RIOT_WEB_CODE_SERVER_URL="https://github.com/coder/code-server/releases/download/v${RIOT_WEB_CODE_SERVER_VERSION}/${RIOT_WEB_CODE_SERVER_PKG}"

RUN echo "Installing coder/code-server" \
    && curl -fOL ${RIOT_WEB_CODE_SERVER_URL} \
    && dpkg -i ${RIOT_WEB_CODE_SERVER_PKG}
ENV XDG_DATA_HOME="${RIOT_WEB_USER_HOME}/.local/share"
ENV XDG_CONFIG_HOME="${RIOT_WEB_USER_HOME}/.config"
COPY --chown=$USERID:$GROUPID "./config/code-server-conf.yaml" "${RIOT_WEB_USER_HOME}/.config/code-server/config.yaml"
COPY --chown=$USERID:$GROUPID "./config/default-vscode-user-settings.json" "${RIOT_WEB_USER_HOME}/.local/share/code-server/User/settings.json"
RUN chown -R $USERNAME:$USERNAME "${RIOT_WEB_USER_HOME}"

# VSCode Extension
ARG RIOT_WEB_VSCODE_EXTENSION_VERSION="0.0.7"
ARG RIOT_WEB_VSCODE_EXTENSION_PKG_SRC="./extensions/RIOT-VS-Code-Extension/extensions/web/riot-web-extension-${RIOT_WEB_VSCODE_EXTENSION_VERSION}.vsix"

ENV RIOT_WEB_VSCODE_EXTENSION_PKG="${RIOT_WEB_USER_HOME}/.local/share/code-server/extensions/riot-web-extension.vsix"

COPY --chown=$USERID:$GROUPID --chmod=775 "${RIOT_WEB_VSCODE_EXTENSION_PKG_SRC}" "${RIOT_WEB_VSCODE_EXTENSION_PKG}"

# Cleanup
RUN echo 'Cleaning up installation files' \
     && apt clean \
     && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /pkgs

# Entrypoint
ARG SRC_DOCKER_ENTRYPOINT="./docker_entrypoint.sh"
COPY --chown=root:root --chmod=775 "${SRC_DOCKER_ENTRYPOINT}" "${RIOT_WEB_TOOLS}/docker_entrypoint.sh"

EXPOSE 8080
USER "${USERNAME}"
ENV HOME="${RIOT_WEB_USER_HOME}"
#TODO: change to shell.py
ENV SHELL="/usr/bin/riot-web/shell.py"
WORKDIR "$HOME"

ENTRYPOINT []
CMD ["/bin/bash","-c","${RIOT_WEB_TOOLS}/docker_entrypoint.sh"]