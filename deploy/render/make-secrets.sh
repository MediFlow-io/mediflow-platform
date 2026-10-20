#!/usr/bin/env bash
# Prints the secrets Render asks for when you create the Blueprint. Run it in Git Bash (or any shell
# with openssl). Paste each value into Render (multi-line values are fine: copy from -----BEGIN to
# -----END----- included). Keep the output private; never commit it.
set -euo pipefail
dir=$(mktemp -d)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/private.pem" 2>/dev/null
openssl rsa -in "$dir/private.pem" -pubout -out "$dir/public.pem" 2>/dev/null
echo "===== JWT_PRIVATE_KEY (service mediflow-io-api)"
cat "$dir/private.pem"
echo
echo "===== JWT_PUBLIC_KEY (service mediflow-io-api)"
cat "$dir/public.pem"
echo
echo "===== APP_KEY (service mediflow-io-admin)"
echo "base64:$(openssl rand -base64 32)"
rm -rf "$dir"
