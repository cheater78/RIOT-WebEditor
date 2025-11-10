[RIOT-OS]: https://github.com/RIOT-OS/RIOT
[RIOT-WEB]: https://github.com/cheater78/RIOT-WEB
[coder/code-server]: https://github.com/coder/code-server
[RIOT-WEB-FLASH-EXT-PROTOTYPE]: https://github.com/cheater78/RIOT-WEB-FLASH-EXT-PROTOTYPE

# [RIOT-OS][RIOT-OS] Web Editor
Project for the RIOT-OS Web Editor, uses:
- [coder/code-server][coder/code-server] (VSCode style Editor)
- [RIOT-OS fork][RIOT-WEB]
- [RIOT-WEB-FLASH-EXT-PROTOTYPE][RIOT-WEB-FLASH-EXT-PROTOTYPE]
## Config [code-server][coder/code-server]
The code-server config file is located at [config/code-server.conf.yaml](config/code-server.conf.yaml)
### set password hash (argon2)
```
# Requires argon2
sudo apt install argon2
# Change to your password
echo -n "changeme" | argon2 "$(head -c16 /dev/urandom | base64)"
# Then use the Encoded string
```
The current password set in [code-server.conf.yaml](config/code-server.conf.yaml) is '**changeme**' for demonstration purposes only.
## Config VSCode
The default vscode user settings file is located at [config/default-vscode-user-settings.json](config/default-vscode-user-settings.json)
It implements already some RIOT conventions, as well as DarkMode for your eyes.

## Log
Project log for what was done, when, why and what went wrong
### Week 01
1. Choosing an IDE backend:
    - "[Monaco](https://github.com/microsoft/monaco-editor)" MS WebEditor (which VSCode is based on)
        - [MS code-server](https://code.visualstudio.com/docs/remote/vscode-server)
            - weirdly sanboxed into VSCode/-CLI
            - not for use as public service
            - requires github login on client and server
        - [coder/code-server][coder/code-server] (viable)
            - this one: easy config, lightweight
        - openvscodeserver (viable)
        - [Eclipse Che](https://eclipse.dev/che/) with Monaco or JetBrains UI (convoluted)
            - [Theia](https://theia-ide.org/): Eclipse Che with AI bloat
    - others exist but generally not for C development or just not as well known as the VSCode look
2. Future considerations:
    - webUSB and webSerial for flashing and comms with chips:
        - for flash: transfer blob to client?
    - remote dev env setup:
        - docker container
        - [coder/code-server][coder/code-server]
        - docker port mapping
    - multi user:
        - docker container startup, shutdown, access - how?
### Week 02
1. WebSerial:
    - Write Test (to Arduino programmed esp32-wroom, readout through other serial console)
    - Read Test (from Arduino programmed esp32-wroom, printing to Serial)
    - Echo Test (esp setup to echo its input, write on Web-Button + async reading loop to web text field)
2. Docker code-server:
    - added non root user
	- fixed perms for home
	- added config
	- currently auto setup for esp (esp-idf)
	- esp-idf vscode web extension?
		- flasher_args.json is speced inline in RIOT cmd esptool write-flash - could possibly grep args from that
3. Tested Flash on native ubuntu with RIOT and [esp-idf](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html) to get familiar with the current workflow
4. Tested the alr existing [esp web extension](https://docs.espressif.com/projects/vscode-esp-idf-extension/en/latest/additionalfeatures/web-extension.html) (a vscode web extension using [esptool.js](https://github.com/espressif/esptool-js))
    - working serial console, after defining project_description.json with "monitor_baud":"115200"
### Week 03
1. esptool dummy:
    - TODO: pull from pp03
2. [esptool.js](https://github.com/espressif/esptool-js) flasher prototype on node
    - build and flasher args export is manual
    - file input is manual
    - flash and erase of esp32-wroom works
3. Noticed porblems:
    - device identification (is non unique) -> vendor + product ID
        - those are writable - even worse -> FIX: user selects device from list
    - WebSerial does not allow device access in non secure (non HTTPS) remote sessions
        - FIX: HTTPS terminating reverse Proxy, also for multi container management
### Week 04
1. TODO: query progess on [RIOT-WEB-FLASH-EXT-PROTOTYPE][RIOT-WEB-FLASH-EXT-PROTOTYPE]
    - ask that other guy
2. Created this repo
3. Reworked Dockerfile
    - now uses base Dockerfile [riot/riotbuild:latest](https://github.com/RIOT-OS/riotdocker)
        - alr contains necessary buildtools
        - more lightweight compiler setup
    - created docker.sh (-b for build, -s to start, -d to debug) for quicker setup
        - image name: riot-dev-env
        - container name: riot-dev-con
        - access port: 80 (mapped to code-servers 8080)
    - clones current [RIOT-WEB-FLASH-EXT-PROTOTYPE][RIOT-WEB-FLASH-EXT-PROTOTYPE] and installs it
        - also provides tools(npm, vsce) to theoretically reload live(code-server --install-extension /path)
    - clones current [RIOT-OS][RIOT-WEB] fork
4. [RIOT-OS][RIOT-WEB] fork
    - TODO: touch make system without going crazy - alr failed
    - found smth at: makefiles/tools/esptool.inc.mk (now search usage)
5. Future considerations:
    - reverse proxy and docker container management tool: [Treafik](https://github.com/traefik/traefik) (under MIT license)
    - or look into [coder](https://github.com/coder/coder)
