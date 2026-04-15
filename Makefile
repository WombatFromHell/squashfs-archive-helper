PROJECT = squashfs-archive-helper
VERSION = 1.4.1
#
SRC_DIR = src
ASSET_DIR = assets
#
DIST_DIR = dist
BUILD_DIR = $(DIST_DIR)/$(PROJECT)
PKG_DIR = artifact
PKG = $(PROJECT)_$(VERSION)
# Fixed epoch for reproducible builds:
# Default to Jan 1, 1980 00:00:00 UTC (315532800) if not set
SOURCE_DATE_EPOCH ?= 315532800
export SOURCE_DATE_EPOCH

clean:
	rm -rf $(DIST_DIR) $(PKG_DIR)

build: clean
	mkdir -p $(BUILD_DIR)
	install -m 755 $(SRC_DIR)/*.sh $(BUILD_DIR)
	install -m 755 $(ASSET_DIR)/install.sh $(BUILD_DIR)
	install -m 755 $(ASSET_DIR)/squashfs-actions.desktop $(BUILD_DIR)
	install -m 644 LICENSE README.md $(BUILD_DIR)
	# Inject version into scripts
	sed -i 's/^VERSION="dev"$$/VERSION="$(VERSION)"/' $(BUILD_DIR)/*.sh
	@echo "Built $(PROJECT) @ $(VERSION) in $(BUILD_DIR)"

install:
	cd $(BUILD_DIR) && ./install.sh

format:
	shfmt -i 2 -ci -bn -w -s $$(find $(SRC_DIR) $(ASSET_DIR) -type f -name "*.sh")
	prettier -w ./*.md ./.github/workflows/*.yml

package: build
	rm -rf $(PKG_DIR) && mkdir -p $(PKG_DIR)
	# Normalize timestamps on all dist files for reproducibility
	find $(BUILD_DIR) -type f -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;
	# Create reproducible tarball with deterministic timestamps and ownership
	# Archives the PROJECT directory from within DIST_DIR to ensure a top-level folder
	tar --sort=name \
		--mtime="@$(SOURCE_DATE_EPOCH)" \
		--owner=0 --group=0 --numeric-owner \
		-czf $(PKG_DIR)/$(PKG).tar.gz -C $(DIST_DIR) $(PROJECT)
	@echo "Created $(PKG_DIR)/$(PKG).tar.gz"
	cd $(PKG_DIR) && \
		sha256sum $(PKG).tar.gz > $(PKG).tar.gz.sha256 && \
		cat $(PKG).tar.gz.sha256 && \
		sha256sum -c $(PKG).tar.gz.sha256

all: clean build install

.PHONY: clean build install format package all
.SILENT: clean build install format package all
