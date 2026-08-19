#!/bin/sh
set -eu

REGION="__GLUPTA_REGION__"
OPENAI_HOST="__GLUPTA_HOST__"
DNSMASQ_CONFIG="/etc/dnsmasq.d/90-glupta-egress.conf"
NFT_TABLE="glupta_egress"

dns_candidate=""
nft_candidate=""
cleanup() {
    status=$?
    trap - EXIT INT TERM
    [ -z "$dns_candidate" ] || rm -f "$dns_candidate"
    [ -z "$nft_candidate" ] || rm -f "$nft_candidate"
    if [ "$status" -ne 0 ]; then
        systemctl stop docker.service docker.socket containerd.service >/dev/null 2>&1 || true
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM

[ "$(id -u)" -eq 0 ]
[ "$REGION:$OPENAI_HOST" = "__GLUPTA_PAIR__" ]
for command in nft dnsmasq install mktemp systemctl; do
    command -v "$command" >/dev/null
done
dnsmasq --version | grep -qw nftset

dns_candidate="$(mktemp /run/glupta-dnsmasq.XXXXXX)"
nft_candidate="$(mktemp /run/glupta-nft.XXXXXX)"
printf 'nftset=/%s/4#inet#%s#openai4\n' "$OPENAI_HOST" "$NFT_TABLE" >"$dns_candidate"
dnsmasq --test --conf-file="$dns_candidate" >/dev/null

if nft list table inet "$NFT_TABLE" >/dev/null 2>&1; then
    printf 'flush table inet %s\n' "$NFT_TABLE" >"$nft_candidate"
fi
cat >>"$nft_candidate" <<'NFT'
table inet glupta_egress {
    set openai4 {
        type ipv4_addr
        flags timeout
        timeout 5m
        size 64
    }
    counter glupta_denied {}
    chain forward {
        type filter hook forward priority filter - 10; policy accept;
        ip saddr 172.30.47.2 ct state established,related accept
        ip saddr 172.30.47.2 ip daddr 172.30.47.3 tcp dport 5432 accept
        ip saddr 172.30.47.2 ip daddr @openai4 tcp dport 443 accept
        ip saddr 172.30.47.2 counter name glupta_denied reject with icmpx type admin-prohibited
    }
}
NFT
nft --check --file "$nft_candidate"

install -o root -g root -m 0644 "$dns_candidate" "$DNSMASQ_CONFIG"
nft --file "$nft_candidate"
systemctl restart dnsmasq
systemctl is-active --quiet dnsmasq
