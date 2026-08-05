#!/bin/sh
# THE ONE STEP: give your local models a frontier-level brain.
# Installs the two bodies, verifies the brain, done.
set -e
command -v cc >/dev/null || { echo "need a C compiler (xcode-select --install)"; exit 1; }
command -v ollama >/dev/null || { echo "install ollama first: https://ollama.com"; exit 1; }
echo "== pulling Body S (semantics): llama3:8b =="
ollama pull llama3:8b
echo "== pulling Body D (raw data): qwen2.5-coder:7b =="
ollama pull qwen2.5-coder:7b
echo "== verifying the brain (offline self-test, includes a full 2^32 proof) =="
python3 frontier/sphere_brain.py selftest
echo ""
echo "READY. Your local models now have the Sphere as brain."
echo "  python3 frontier/sphere_brain.py solve spec.txt your.log \"your intent in one sentence\""
