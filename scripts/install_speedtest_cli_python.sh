#!/usr/bin/env bash
set -euo pipefail

# Install python-based speedtest-cli into the project using uv
cd ~/code/phronetics/streambox
uv add speedtest-cli
