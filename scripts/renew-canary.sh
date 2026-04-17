#!/usr/bin/env bash
set -euo pipefail

# Renew the ai-for-less-suffering.com warrant canary.
# Fetches the latest Bitcoin block, updates dates, and signs the statement.
#
# Usage: ./scripts/renew-canary.sh [--fingerprint FINGERPRINT]
#
# Prerequisites:
#   - gpg key for canary@ai-for-less-suffering.com must exist in the local keyring
#   - curl must be installed
#   - running on Linux (uses GNU sed / GNU date)

CANARY="public/canary.txt"
SIG="public/canary.txt.asc"
SIGNER="canary@ai-for-less-suffering.com"
VALIDITY_DAYS=1095  # 3 years

FINGERPRINT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --fingerprint) FINGERPRINT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ! -f "$CANARY" ]]; then
  echo "ERROR: $CANARY not found. Run from repo root."
  exit 1
fi

if [[ -z "$FINGERPRINT" ]]; then
  FINGERPRINT=$(gpg --with-colons --fingerprint "$SIGNER" 2>/dev/null \
    | awk -F: '/^fpr:/{print $10; exit}' || true)
  if [[ -z "$FINGERPRINT" ]]; then
    echo "ERROR: No GPG key found for $SIGNER" >&2
    echo "Generate one first: gpg --full-generate-key" >&2
    exit 1
  fi
fi

FP_FORMATTED=$(echo "$FINGERPRINT" | sed 's/.\{4\}/& /g' | sed 's/ $//')

echo "Fetching latest Bitcoin block..."
BLOCK_HEIGHT=$(curl -sf --max-time 10 https://mempool.space/api/blocks/tip/height)
BLOCK_HASH=$(curl -sf --max-time 10 https://mempool.space/api/blocks/tip/hash)

if [[ -z "$BLOCK_HEIGHT" || -z "$BLOCK_HASH" ]]; then
  echo "ERROR: Failed to fetch Bitcoin block data from mempool.space"
  exit 1
fi

echo "  Block height: $BLOCK_HEIGHT"
echo "  Block hash:   $BLOCK_HASH"

ISSUED=$(date -u +%Y-%m-%d)
EXPIRES=$(date -u -d "+${VALIDITY_DAYS} days" +%Y-%m-%d)

echo "  Issued:  $ISSUED"
echo "  Expires: $EXPIRES"

sed -i "s|^Issued[[:space:]]*:.*|Issued        : $ISSUED|" "$CANARY"
sed -i "s|^Expires[[:space:]]*:.*|Expires       : $EXPIRES|" "$CANARY"
sed -i "s|^Block height[[:space:]]*:.*|Block height  : $BLOCK_HEIGHT|" "$CANARY"
sed -i "s|^Block hash[[:space:]]*:.*|Block hash    : $BLOCK_HASH|" "$CANARY"
sed -i "s|^Fingerprint[[:space:]]*:.*|Fingerprint   : $FP_FORMATTED|" "$CANARY"

echo "Updated $CANARY"

# Kill gpg-agent so signing always prompts for the passphrase --- the canary
# attestation should require a conscious human act, not a cached credential.
gpgconf --kill gpg-agent 2>/dev/null || true

gpg --armor --detach-sign --yes -u "$SIGNER" --output "$SIG" "$CANARY"
echo "Signed: $SIG"

echo ""
echo "Verifying..."
gpg --verify "$SIG" "$CANARY"
echo ""
echo "Done. Review the changes, then commit and deploy."
