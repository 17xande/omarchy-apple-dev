#!/usr/bin/env bash
# chk-undef.sh <object>: list the Foundation / ObjC-class symbols the object needs that the sysroot's link
# stubs (.tbd, cut from the connected iPhone by sdk-free/setup.sh) do not list — a missing one would fail to
# link here or fail to load on the phone.
#   sdk-free/swift/chk-undef.sh build/ios-sdkfree/release/obj/swiftplugin-Shared.o
set -euo pipefail
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
O=${1:?usage: chk-undef.sh <object file>}
SWIFTC=$(command -v swiftc)
TC=$(dirname "$(dirname "$(readlink -f "$SWIFTC")")")
NM=$TC/bin/llvm-nm
[ -x "$NM" ] || NM=$TC/bin/llvm-nm
undef=$(mktemp)
trap 'rm -f "$undef"' EXIT
"$NM" -u "$O" | grep -E '10Foundation|_OBJC_CLASS_\$_(NS|UI|SF|CF|CA)|_NS[A-Z]|_UI[A-Z]|_SF[A-Z]|_CF[A-Z]' | sed 's/^ *U //' | sort -u >"$undef" || true
miss=0
while read -r s; do
  [ -n "$s" ] || continue
  case "$s" in
    _OBJC_CLASS_\$_*) n=${s#_OBJC_CLASS_\$_}; grep -qw -- "$n" "$SR"/System/Library/Frameworks/*/*.tbd "$SR"/usr/lib/*.tbd 2>/dev/null && continue ;;
    *) grep -qF -- "$s" "$SR"/System/Library/Frameworks/*/*.tbd "$SR"/usr/lib/*.tbd 2>/dev/null && continue ;;
  esac
  echo "MISSING $s"
  miss=$((miss + 1))
done <"$undef"
echo "checked $(wc -l <"$undef") symbols, missing $miss"
[ "$miss" -eq 0 ]
