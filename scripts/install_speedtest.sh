#!/bin/bash

# check and install curl
if ! command -v curl >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y curl
fi

# check and install speedtest-cli
if ! command -v speedtest >/dev/null; then
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
    sudo apt-get install -y speedtest
fi
