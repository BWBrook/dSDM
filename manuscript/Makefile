PROFILE ?= draft
.DEFAULT_GOAL := all
MAKEDOC ?= $(abspath ../../../work/makedoc)
CONFIG ?= $(abspath settings/build.yaml)
BUILD_ENV := $(abspath .venv)
export PATH := $(BUILD_ENV)/bin:$(PATH)
PROFILE_CACHE_DIR ?= $(abspath .cache/$(PROFILE))
PDF_ENGINE_OUTPUT_DIR ?= $(PROFILE_CACHE_DIR)/latex

.PHONY: setup all pdf docx manifest check validate profiles profile-show clean

setup:
	uv venv --allow-existing --python 3.12 "$(BUILD_ENV)"
	uv pip install --python "$(BUILD_ENV)/bin/python" -r requirements-build.txt

DOCX_FORMATTER ?= ../scripts/format_review_docx.py
WORD_OUTPUT_STEM := $(if $(filter supplement,$(PROFILE)),dsdm_supplement,dsdm_manuscript)
WORD_DOCX := build/$(WORD_OUTPUT_STEM).docx

all:
	$(MAKE) pdf CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) -C "$(MAKEDOC)" manifest CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

pdf:
	$(MAKE) -C "$(MAKEDOC)" pdf CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

docx:
	$(MAKE) -C "$(MAKEDOC)" docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"
	python3 "$(DOCX_FORMATTER)" --docx "$(WORD_DOCX)"

manifest:
	$(MAKE) docx CONFIG="$(CONFIG)" PROFILE="$(PROFILE)"
	$(MAKE) -C "$(MAKEDOC)" manifest CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

check:
	$(MAKE) -C "$(MAKEDOC)" check CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

validate:
	$(MAKE) -C "$(MAKEDOC)" validate-config CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

profiles:
	$(MAKE) -C "$(MAKEDOC)" profiles CONFIG="$(CONFIG)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

profile-show:
	$(MAKE) -C "$(MAKEDOC)" profile-show CONFIG="$(CONFIG)" PROFILE="$(PROFILE)" PROFILE_CACHE_DIR="$(PROFILE_CACHE_DIR)" PDF_ENGINE_OUTPUT_DIR="$(PDF_ENGINE_OUTPUT_DIR)"

clean:
	rm -rf build .cache
