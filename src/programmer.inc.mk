# Configure the programmer related variables

PROGRAMMER_QUIET ?= $(QUIET)
ifeq (0,$(PROGRAMMER_QUIET))
  PROGRAMMER_VERBOSE_OPT ?= --verbose
endif

# Don't use the programmer wrapper by default
USE_PROGRAMMER_WRAPPER_SCRIPT ?= 0

ifeq (1,$(USE_PROGRAMMER_WRAPPER_SCRIPT))
  PROGRAMMER_FLASH ?= @$(RIOTTOOLS)/programmer/programmer.py \
    --action Flashing --cmd "$(FLASHER) $(FFLAGS)" \
    --programmer "$(PROGRAMMER)" $(PROGRAMMER_VERBOSE_OPT)
  PROGRAMMER_RESET ?= @$(RIOTTOOLS)/programmer/programmer.py \
  --action Resetting --cmd "$(RESET) $(RESET_FLAGS)" \
  --programmer "$(PROGRAMMER)" $(PROGRAMMER_VERBOSE_OPT)
else ifeq (1,$(RIOT_FLASH_WEB))
  PROGRAMMER_FLASH = @$(RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_WRITE) \
  flash \
	"$(BOARD)" \
  "$(PROGRAMMER)" $(PROGRAMMER_VERBOSE_OPT) \
	"$(FLASHER) $(FFLAGS)" \
  PROGRAMMER_RESET = @$(RIOT_WEB_RUNTIME_WEBSOCKET_SCRIPT_WS_WRITE) \
  reset \
	"$(BOARD)" \
  "$(PROGRAMMER)" $(PROGRAMMER_VERBOSE_OPT) \
	"$(RESET) $(RESET_FLAGS)"
else
  PROGRAMMER_FLASH ?= $(FLASHER) $(FFLAGS)
  PROGRAMMER_RESET ?= $(RESET) $(RESET_FLAGS)
endif
