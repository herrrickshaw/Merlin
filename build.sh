#!/bin/bash

# Simple build script for Merlin (requires OCaml 4.14+)

set -e

OCAMLOPT="${OCAMLOPT:-ocamlopt}"
OCAMLFIND="${OCAMLFIND:-ocamlfind}"

# Check OCaml
echo "Checking OCaml..."
$OCAMLOPT -version || { echo "OCamlopt not found. Install OCaml 4.14+"; exit 1; }

# Create output directory
mkdir -p _build/lib _build/bin

echo "Building Merlin library..."

# Compile library modules
$OCAMLFIND $OCAMLOPT -c -package yojson,str,unix \
  -thread -o _build/lib/data.cmx lib/data.ml 2>&1 || true

$OCAMLFIND $OCAMLOPT -c -package yojson,str,unix \
  -thread -o _build/lib/analyze.cmx lib/analyze.ml 2>&1 || true

$OCAMLFIND $OCAMLOPT -c -package yojson,str,unix \
  -thread -o _build/lib/uploader.cmx lib/uploader.ml 2>&1 || true

echo "Building executable..."

# Compile main executable
$OCAMLFIND $OCAMLOPT -package yojson,str,unix -linkpkg \
  -thread -o _build/bin/merlin \
  _build/lib/data.cmx _build/lib/analyze.cmx _build/lib/uploader.cmx \
  bin/merlin.ml 2>&1 || true

if [ -f "_build/bin/merlin" ]; then
    echo "✓ Build successful!"
    echo "Binary: _build/bin/merlin"
    echo ""
    echo "Usage:"
    echo "  ./_build/bin/merlin help"
else
    echo "✗ Build failed"
    exit 1
fi
