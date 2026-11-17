#!/bin/sh
# Retries creating the Always Free Ampere A1 instance until Oracle has capacity, then stops.
# "Out of host capacity" is a known limit of the free offer: a slot frees up when another
# user deletes a machine, so the only option is to keep asking (every few minutes, no faster).
# Tries 2 OCPU / 12 GB first, then 1 OCPU / 6 GB. On success the instance JSON is saved to
# $OCI_DIR/instance.json and the loop exits.
OCI_DIR=${OCI_DIR:-/oracle/.oci}
. "$OCI_DIR/agriprix.env"
DONE="$OCI_DIR/instance.json"
n=0
while [ ! -s "$DONE" ]; do
  for size in "2 12" "1 6"; do
    set -- $size
    n=$((n + 1))
    out=$(oci compute instance launch -c "$C" --availability-domain "$AD" --display-name agriprix \
      --shape VM.Standard.A1.Flex --shape-config "{\"ocpus\":$1,\"memoryInGBs\":$2}" \
      --image-id "$IMG" --subnet-id "$SUB" --assign-public-ip true \
      --boot-volume-size-in-gbs 50 --ssh-authorized-keys-file "$OCI_DIR/ssh_key.pub" 2>&1)
    if echo "$out" | grep -q '"lifecycle-state"'; then
      echo "$out" > "$DONE"
      echo "$(date -u +%FT%TZ) attempt $n: SUCCESS with $1 OCPU / $2 GB"
      exit 0
    fi
    reason=$(echo "$out" | grep -o '"message": "[^"]*"' | head -1)
    echo "$(date -u +%FT%TZ) attempt $n ($1 OCPU/$2 GB): ${reason:-$(echo "$out" | tail -1)}"
    sleep 20
  done
  sleep 120
done
