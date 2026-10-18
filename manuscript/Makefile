PROFILE ?= draft
MAKEDOC ?= $(abspath ../../../work/makedoc)
CONFIG ?= $(abspath settings/build.yaml)

.PHONY: all pdf docx manifest check validate profiles profile-show clean

DOCX_FORMATTER ?= ../scripts/format_review_docx.py
WORD_OUTPUT_STEM := $(if $(filter supplement,$(PROFILE)),dsdm_supplement,dsdm_manuscript)
WORD_DOCX := build/$(WORD_OUTPUT_STEM).docx

all:
	$(MAKE) pdf CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) -C "$(MAKEDOC)" manifest CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

pdf:
	$(MAKE) -C "$(MAKEDOC)" pdf CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

docx:
	$(MAKE) -C "$(MAKEDOC)" docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	python3 "$(DOCX_FORMATTER)" --docx "$(WORD_DOCX)"

manifest:
	$(MAKE) docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) -C "$(MAKEDOC)" manifest CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

check:
	$(MAKE) -C "$(MAKEDOC)" check CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

validate:
	$(MAKE) -C "$(MAKEDOC)" validate-config CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

profiles:
	$(MAKE) -C "$(MAKEDOC)" profiles CONFIG="$(CONFIG)"

profile-show:
	$(MAKE) -C "$(MAKEDOC)" profile-show CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"

clean:
	rm -rf build .cache
