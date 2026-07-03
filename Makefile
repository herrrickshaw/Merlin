.PHONY: build install test clean help

build:
	dune build

install:
	dune install

dev:
	dune build @all --watch

test:
	dune runtest

run:
	dune exec bin/merlin.exe

clean:
	dune clean

help:
	@echo "Merlin - LFS Data Analyzer"
	@echo ""
	@echo "Targets:"
	@echo "  build    - Build the project"
	@echo "  install  - Install the binary"
	@echo "  dev      - Watch mode"
	@echo "  test     - Run tests"
	@echo "  run      - Run merlin"
	@echo "  clean    - Clean build files"
