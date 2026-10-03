#!/usr/bin/env bash
# Run an xtool project on an iPhone from Omarchy Linux.
# Run this from inside your xtool project directory (the one with xtool.yml).
# First run ever: do `xtool auth` once beforehand (interactive Apple ID sign-in).
#
# Modes:
#   ./device-run.sh                        USB (default; the proven path)
#   ./device-run.sh --network [--udid U]   WiFi, phone on the SAME network.
#       TESTED EXHAUSTIVELY 2026-09-16 on iOS 26.6.2: BLOCKED for hosts the
#       phone has no RemotePairing tunnel with. iOS gives every host its own
#       encrypted tunnel (`<uuid>._rp-tunnel._tcp`, ephemeral port), accepts
#       nobody else, and offers no device-side pairing screen to add a host
#       (that flow is iOS 27+). A Mac that once enabled "Connect via Network"
#       keeps a working wireless tunnel; a Linux host cannot get one today.
#       Full evidence in FINDINGS.md 17. Use USB, or the tunneld bridge below
#       through a Mac that holds the tunnel.
#   ./device-run.sh --rsd HOST PORT PKG    install+launch an already-signed
#       .app/.ipa against an explicit RemoteServiceDiscovery address. Works
#       against tunnels you DO hold: the RSD endpoint printed by
#       `sudo pymobiledevice3 lockdown start-tunnel` (USB) or a tunneld
#       instance. Addressing the phone's WiFi interfaces directly does not
#       work on iOS 26 (per-host tunnel gating, FINDINGS.md 17).
#       PKG must be signed with a real certificate: xtool's free-provisioning
#       signing only happens inside `xtool dev run`.
#
# Tailscale: mDNS discovery does not cross tailscale0, and Apple's remoted
# binds the phone's LAN interface, so a phone reachable only via Tailscale is
# not directly deployable. The supported remote pattern is pymobiledevice3's
# tunneld WebSocket bridge -- on a machine that CAN see the phone (USB or
# same LAN):
#     sudo pymobiledevice3 remote tunneld        # prints its WS port
# then, from the remote host:
#     pymobiledevice3 apps install PKG --tunnel UDID@BRIDGE_HOST:WS_PORT
#     pymobiledevice3 developer core-device launch-application BID "" \
#         --tunnel UDID@BRIDGE_HOST:WS_PORT
set -euo pipefail
# The toolchain's own bin dir (lldb) first: /usr/lib/swift/bin on swift-bin
# 6.3, /usr/lib/swift/usr/bin on 6.4, elsewhere under mise.
PATH="$(dirname "$(readlink -f "$(command -v swift)")"):$PATH"
export PATH

XT="$HOME/.local/bin/xtool"
PMD3="$HOME/pymobile3-venv/bin/pymobiledevice3"

MODE=usb; UDID=; RSD_HOST=; RSD_PORT=; PKG=
while [ $# -gt 0 ]; do
  case "$1" in
    --network) MODE=network ;;
    -u|--udid) UDID="${2:?--udid needs a value}"; shift ;;
    --rsd) MODE=rsd
      RSD_HOST="${2:?usage: --rsd HOST PORT PACKAGE}"
      RSD_PORT="${3:?usage: --rsd HOST PORT PACKAGE}"
      PKG="${4:?usage: --rsd HOST PORT PACKAGE}"
      shift 3 ;;
    *) echo "Unknown argument: $1 (modes: [--network] [--rsd HOST PORT PKG])" >&2; exit 2 ;;
  esac
  shift
done

UDID_ARGS=()
if [ -n "$UDID" ]; then UDID_ARGS=(--udid "$UDID"); fi

case "$MODE" in
usb)
  echo "== 1. Device visible over USB? =="
  # usbmuxd is started by udev when a device is plugged in. Nothing to enable.
  lsusb | grep -i apple || echo "WARNING: no Apple USB device found by lsusb."

  echo "== 2. Trust and pair =="
  # The phone shows a 'Trust This Computer' prompt on first connect. Accept it.
  $PMD3 lockdown info >/dev/null 2>&1 \
    && echo "Lockdown reachable, pairing OK." \
    || { echo "Pairing needed: run '$PMD3 lockdown pair' and accept the prompt on the phone."; }

  echo "== 3. List devices via xtool =="
  $XT devices "${UDID_ARGS[@]}"

  echo "== 4. Build, sign, install, launch =="
  # xtool dev run does all four. Signing uses your Apple ID (free tier works);
  # the first deploy creates a free provisioning profile for your device.
  $XT dev run "${UDID_ARGS[@]}"

  echo "== 5. LLDB attach =="
  # The Swift toolchain lldb has the remote-ios platform. Attach workflow,
  # from an interactive lldb session (adjust as needed):
  #   lldb
  #   (lldb) platform select remote-ios
  #   (lldb) platform connect <connect:// URL printed by xtool>
  #   (lldb) process attach --name HelloOmarchy
  #   (lldb) b ContentView.swift:12
  #   (lldb) c
  # pymobiledevice3 can also reach the developer services; on iOS 17+ the
  # proven flow is in FINDINGS.md items 10-13 (mounter, sudo start-tunnel,
  # debugserver lldb <bundle-id> --rsd <addr> <port>).
  ;;
network)
  echo "== WiFi deploy (phone on the same network) -- UNVERIFIED =="
  echo "Expects: paired over USB once, Developer Mode on, same LAN segment."
  $XT devices --network
  $XT dev run --network "${UDID_ARGS[@]}"
  ;;
rsd)
  echo "== Install/launch via RSD $RSD_HOST:$RSD_PORT -- UNVERIFIED =="
  $PMD3 apps install "$PKG" --rsd "$RSD_HOST" "$RSD_PORT"
  BID=$(grep -E '^bundleID:' xtool.yml | awk '{print $2}')
  if [ -z "$BID" ]; then echo "No bundle_id in xtool.yml; launch it by hand:"; else
    $PMD3 developer core-device launch-application "$BID" "" --rsd "$RSD_HOST" "$RSD_PORT"
  fi
  ;;
esac
