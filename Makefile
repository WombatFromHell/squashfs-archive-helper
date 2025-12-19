PY = python3
SRC_DIR = src
BUILD_DIR = dist
ENTRY = entry:main
PKG = squish
OUT = $(BUILD_DIR)/$(PKG).pyz

build:
	mkdir -p $(BUILD_DIR)
	$(PY) -m zipapp $(SRC_DIR) -o $(OUT) -m $(ENTRY) -p "/usr/bin/env python3"
	chmod +x $(OUT)

install: $(OUT)
	REAL_HOME="$$(realpath "$$HOME")"; \
	if [ -d "$$REAL_HOME/.local/bin/scripts/" ]; then \
		INSTALL_DIR="$$REAL_HOME/.local/bin/scripts"; \
	else \
		mkdir -p "$$REAL_HOME/.local/bin"; \
		INSTALL_DIR="$$REAL_HOME/.local/bin"; \
	fi; \
	cp $(OUT) "$$INSTALL_DIR/$(PKG).pyz"; \
	chmod +x "$$INSTALL_DIR/$(PKG).pyz"; \
	ln -sf "$$INSTALL_DIR/$(PKG).pyz" "$$REAL_HOME/.local/bin/$(PKG)"; \
	echo "Installed to $$INSTALL_DIR/$(PKG).pyz"; \
	mkdir -p "$$REAL_HOME/.local/share/kio/servicemenus/"; \
	cp -f squashfs-actions.desktop "$$REAL_HOME/.local/share/kio/servicemenus/squashfs-actions.desktop"; \
	kbuildsycoca5 --noincremental; \
	echo "Installed servicemenu to $$REAL_HOME/.local/share/kio/servicemenus/squashfs-actions.desktop"

test:
	uv run pytest -xvs --cov=src --cov-report=term-missing --cov-branch --tb=short

lint:
	ruff check ./src ./tests; \
		pyright ./src ./tests

prettier:
	prettier --cache -c -w *.md

format: prettier
	ruff check --select I ./src ./tests --fix; \
	ruff format ./src ./tests

quality: lint format

radon:
	uv run radon cc ./src/$(PKG)/ -a

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
		$(BUILD_DIR) \
		.pytest_cache \
		.ruff_cache \
		.coverage \
		/tmp/tmp*.mounted

all: clean build install

.PHONY: all clean install build test lint format radon
