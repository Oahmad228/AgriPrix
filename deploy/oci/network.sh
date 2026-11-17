#!/bin/sh
# Creates the AgriPrix network on Oracle Cloud with the OCI CLI:
# VCN, internet gateway, default route, security list (22/80/443 only) and a public subnet.
# Writes the identifiers needed by retry.sh to $OCI_DIR/agriprix.env.
# Run it once, inside the official OCI CLI image (see docs/deploiement.md, section 2 bis).
set -eu
OCI_DIR=${OCI_DIR:-/oracle/.oci}
C=$(grep '^tenancy=' "$OCI_DIR/config" | cut -d= -f2)
AD=$(oci iam availability-domain list --query 'data[0].name' --raw-output)

VCN=$(oci network vcn create -c "$C" --display-name agriprix-vcn --cidr-blocks '["10.0.0.0/16"]' \
      --dns-label agriprix --wait-for-state AVAILABLE --query 'data.id' --raw-output)
IGW=$(oci network internet-gateway create -c "$C" --vcn-id "$VCN" --display-name agriprix-igw \
      --is-enabled true --wait-for-state AVAILABLE --query 'data.id' --raw-output)
RT=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)
oci network route-table update --rt-id "$RT" --force \
  --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW\"}]" >/dev/null
SL=$(oci network security-list create -c "$C" --vcn-id "$VCN" --display-name agriprix-sl \
  --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all","isStateless":false}]' \
  --ingress-security-rules '[
    {"source":"0.0.0.0/0","protocol":"6","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
    {"source":"0.0.0.0/0","protocol":"6","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":80,"max":80}}},
    {"source":"0.0.0.0/0","protocol":"6","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":443,"max":443}}},
    {"source":"0.0.0.0/0","protocol":"1","isStateless":false,"icmpOptions":{"type":3,"code":4}}]' \
  --wait-for-state AVAILABLE --query 'data.id' --raw-output)
SUB=$(oci network subnet create -c "$C" --vcn-id "$VCN" --display-name agriprix-public \
      --cidr-block 10.0.0.0/24 --dns-label pub --route-table-id "$RT" --security-list-ids "[\"$SL\"]" \
      --prohibit-public-ip-on-vnic false --wait-for-state AVAILABLE --query 'data.id' --raw-output)
IMG=$(oci compute image list -c "$C" --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
      --shape VM.Standard.A1.Flex --sort-by TIMECREATED --sort-order DESC --query 'data[0].id' --raw-output)
printf 'C=%s\nAD=%s\nSUB=%s\nIMG=%s\n' "$C" "$AD" "$SUB" "$IMG" > "$OCI_DIR/agriprix.env"
cat "$OCI_DIR/agriprix.env"
