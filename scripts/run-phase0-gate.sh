#!/bin/bash
set -euo pipefail

export PATH="$PATH:/usr/local/go/bin:$HOME/go/bin:$HOME/.local/bin"

cd /mnt/c/Users/dell/Desktop/coco
bash tests/security/gate-phase0.sh
