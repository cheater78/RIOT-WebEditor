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
else
  PROGRAMMER_FLASH ?= $(FLASHER) $(FFLAGS)
  PROGRAMMER_RESET ?= $(RESET) $(RESET_FLAGS)
endif

ifeq (1,$(RIOT_WEB))
  ifeq (esptool,$(PROGRAMMER))
    BINARIES={\"$(BOOTLOADER_POS)\":\"$(BOOTLOADER_BIN)\",\"0x8000\":\"$(BINDIR)/partitions.bin\",\"$(FLASHFILE_POS)\":\"$(FLASHFILE)\"}
  else ifeq (dfu,$(PROGRAMMER))
    BINARIES={\"0x00\":\"$(FLASHFILE)\"}
  else
    BINARIES={}
  endif
  
  PROGRAMMER_FLASH = $(RIOT_WEB_TOOL_STUB) \
  "flash" \
  "$(PORT)" \
	"$(BOARD)" \
  "$(PROGRAMMER)" \
  "$(BINARIES)" \
	"$(FFLAGS)"

  PROGRAMMER_RESET = ""
endif