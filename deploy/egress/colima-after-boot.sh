#!/bin/sh
set -eu
umask 077

MODEL_HOST="__GLUPTA_MODEL_HOST__"
AUTH_HOST="__GLUPTA_AUTH_HOST__"
DNSMASQ_CONFIG="/etc/dnsmasq.d/90-glupta-egress.conf"
NFT_TABLE="glupta_egress"
SERVICE_NAME="glupta-egress.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
SCRIPT_PATH="/usr/local/sbin/glupta-egress-apply"
DROPIN_NAME="90-glupta-egress.conf"

dns_candidate=""
nft_candidate=""
service_candidate=""
dropin_candidate=""
cleanup() {
    exit_code=$?
    trap - EXIT INT TERM
    [ -z "$dns_candidate" ] || rm -f "$dns_candidate"
    [ -z "$nft_candidate" ] || rm -f "$nft_candidate"
    [ -z "$service_candidate" ] || rm -f "$service_candidate"
    [ -z "$dropin_candidate" ] || rm -f "$dropin_candidate"
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

[ "$(id -u)" -eq 0 ]
[ "$MODEL_HOST:$AUTH_HOST" = "__GLUPTA_HOST_PAIR__" ]

apply_egress() {
    nft_candidate="$(mktemp /run/glupta-nft.XXXXXX)"

    # Fail closed for the app address before DNS, package, or service setup.
    if nft list table inet "$NFT_TABLE" >/dev/null 2>&1; then
        printf 'delete table inet %s\n' "$NFT_TABLE" >"$nft_candidate"
    fi
    cat >>"$nft_candidate" <<'NFT'
table inet glupta_egress {
    chain forward {
        type filter hook forward priority filter - 10; policy accept;
        ip saddr 172.30.47.2 reject with icmpx type admin-prohibited
    }
}
NFT
    nft --file "$nft_candidate"

    for command in dnsmasq install systemctl; do
        command -v "$command" >/dev/null
    done
    dnsmasq --version | grep -qw nftset

    dns_candidate="$(mktemp /run/glupta-dnsmasq.XXXXXX)"
    printf 'nftset=/%s/4#inet#%s#codex4\nnftset=/%s/4#inet#%s#codex4\n' \
        "$MODEL_HOST" "$NFT_TABLE" "$AUTH_HOST" "$NFT_TABLE" >"$dns_candidate"
    dnsmasq --test --conf-file=/dev/null --conf-file="$dns_candidate" >/dev/null

    printf 'delete table inet %s\n' "$NFT_TABLE" >"$nft_candidate"
    cat >>"$nft_candidate" <<'NFT'
table inet glupta_egress {
    set codex4 {
        type ipv4_addr
        flags timeout
        timeout 5m
        size 128
    }
    counter glupta_denied {}
    chain forward {
        type filter hook forward priority filter - 10; policy accept;
        ip saddr 172.30.47.2 ct state established,related accept
        ip saddr 172.30.47.2 ip daddr 172.30.47.3 tcp dport 5432 accept
        ip saddr 172.30.47.2 ip daddr @codex4 tcp dport 443 accept
        ip saddr 172.30.47.2 counter name glupta_denied reject with icmpx type admin-prohibited
    }
}
NFT
    nft --check --file "$nft_candidate"
    install -o root -g root -m 0644 "$dns_candidate" "$DNSMASQ_CONFIG"
    nft --file "$nft_candidate"
    systemctl restart dnsmasq
    systemctl is-active --quiet dnsmasq
}

if [ "${1:-}" = "--apply" ]; then
    [ "$#" -eq 1 ]
    apply_egress
    exit 0
fi
[ "$#" -eq 0 ]

for command in cmp install mktemp systemctl; do
    command -v "$command" >/dev/null
done

service_candidate="$(mktemp /run/glupta-egress-service.XXXXXX)"
cat >"$service_candidate" <<'UNIT'
[Unit]
Description=Apply Glupta fail-closed egress policy
Before=docker.service docker.socket containerd.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/glupta-egress-apply --apply
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

dropin_candidate="$(mktemp /run/glupta-egress-dropin.XXXXXX)"
cat >"$dropin_candidate" <<'UNIT'
[Unit]
Requires=glupta-egress.service
After=glupta-egress.service
UNIT

installed=1
[ -x "$SCRIPT_PATH" ] && cmp -s "$0" "$SCRIPT_PATH" || installed=0
[ -f "$SERVICE_PATH" ] && cmp -s "$service_candidate" "$SERVICE_PATH" || installed=0
for unit in docker.service docker.socket containerd.service; do
    dropin_dir="/etc/systemd/system/${unit}.d"
    [ -f "$dropin_dir/$DROPIN_NAME" ] \
        && cmp -s "$dropin_candidate" "$dropin_dir/$DROPIN_NAME" \
        || installed=0
done
if [ "$installed" -eq 1 ] \
    && systemctl is-enabled --quiet "$SERVICE_NAME" \
    && systemctl is-active --quiet "$SERVICE_NAME"; then
    exit 0
fi

# First application is performed only while the app is down. Persist the mask
# before changing the boot dependency so any interrupted installation also
# leaves every later boot closed. An exact active installation is skipped above.
systemctl mask --now docker.service docker.socket containerd.service

install -o root -g root -m 0755 "$0" "$SCRIPT_PATH"
install -o root -g root -m 0644 "$service_candidate" "$SERVICE_PATH"
for unit in docker.service docker.socket containerd.service; do
    dropin_dir="/etc/systemd/system/${unit}.d"
    install -d -o root -g root -m 0755 "$dropin_dir"
    install -o root -g root -m 0644 "$dropin_candidate" "$dropin_dir/$DROPIN_NAME"
done

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"
systemctl unmask docker.service docker.socket containerd.service
