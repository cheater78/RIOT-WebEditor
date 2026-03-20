FLASHFILE = $(HEXFILE).zip
FLASHDEPS += $(HEXFILE).zip
FLASHER := 
FFLAGS := 

%.hex.zip: %.hex
	$(call check_cmd,adafruit-nrfutil,Flash program and preparation tool)
	adafruit-nrfutil dfu genpkg $(ADANRFUTIL_FLAGS) --application $< $@