[RIOT-OS]: https://github.com/RIOT-OS/RIOT
[RIOT-WebEditor]: https://github.com/cheater78/RIOT-WebEditor
[coder/code-server]: https://github.com/coder/code-server
[RIOT-VS-Code-Extension]: https://github.com/Barkolores/RIOT-VS-Code-Extension

# [RIOT-OS][RIOT-OS] Web Editor
Project for the RIOT-OS Web Editor, uses:
- [coder/code-server][coder/code-server] (VSCode style Editor)
- [RIOT-OS fork][RIOT-WEB]
- [RIOT-VS-Code-Extension][RIOT-VS-Code-Extension]

## Install / Deploy
### Prerequisites
- docker
- [RIOT-VS-Code-Extension][RIOT-VS-Code-Extension] submodule, by either:
    -  ``` --recurse ``` during clone
    - or afterwards ``` git submodule update --init ```

### Steps
as root, run:
1. ``` chmod +x ./setup.sh && ./setup.sh ```
2. ``` ./docker.sh -b -s ```


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
The current password set in [code-server.conf.yaml](config/code-server.conf.yaml) is **changeme** for demonstration purposes only.
Leave unset for no password.
## Config VSCode
The default vscode user settings file is located at [config/default-vscode-user-settings.json](config/default-vscode-user-settings.json)

Current features:
- RIOT convention: line ruler
- DarkMode for your eye balls
- Riot-Web-Shell for interactive Web UX

## docker.sh helper script
builds and runs the [RIOT-WebEditor][RIOT-WebEditor] docker image
- -b: build
- -s: start
- -u: update [RIOT-VS-Code-Extension][RIOT-VS-Code-Extension]
- -n: skip [RIOT-VS-Code-Extension][RIOT-VS-Code-Extension] packaging
- -d: debug/no cache

## Supported Boards (by flasher)
- esptool:
    - esp32c3-devkit
    - esp32c3-wemos-mini
    - esp32c6-devkit
    - esp32-ethernet-kit-v1_0
    - esp32-ethernet-kit-v1_1
    - esp32-ethernet-kit-v1_2
    - esp32h2-devkit
    - esp32-heltec-lora32-v2
    - esp32-mh-et-live-minikit
    - esp32-olimex-evb
    - esp32s2-devkit
    - esp32s2-lilygo-ttgo-t8
    - esp32s2-wemos-mini
    - esp32s3-box
    - esp32s3-devkit
    - esp32s3-pros3
    - esp32s3-usb-otg
    - esp32s3-wt32-sc01-plus
    - esp32-ttgo-t-beam
    - esp32-wemos-d1-r32
    - esp32-wemos-lolin-d32-pro
    - esp32-wroom-32
    - esp32-wrover-kit
    - esp8266-esp-12x
    - esp8266-olimex-mod
    - esp8266-sparkfun-thing
    - seeedstudio-xiao-esp32c3
    - seeedstudio-xiao-esp32s3
- adafruit-nrfutil:
    - adafruit-clue
    - adafruit-feather-nrf52840-express
    - adafruit-feather-nrf52840-sense
    - adafruit-itsybitsy-nrf52
    - pro-micro-nrf52840
    - seeedstudio-xiao-nrf52840-sense
    - seeedstudio-xiao-nrf52840

## Design considerations


## Open issues
