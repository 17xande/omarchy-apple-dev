#!/usr/bin/env python3
"""Development signing identity for one iOS bundle id and one device, through the App Store Connect API.

usage: provision-dev.py --bundle-id ID --udid UDID [--name NAME] [--out DIR]

Needs ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH, like ship.sh. It makes a local RSA key and a CSR, asks
Apple for an iOS Development certificate, registers the device, registers the bundle id, and creates an
IOS_APP_DEVELOPMENT profile that holds both. Output in DIR (default ~/.config/omarchy-apple-dev/development):
key.pem (mode 600, never printed), cert.der, cert.pem, certificate-id, <bundle id>.mobileprovision.
Run again to reuse the key and certificate and refresh the profile."""
import argparse
import base64
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asc  # noqa: E402


def certificate(out):
    key_path, cert_path = out / "key.pem", out / "cert.der"
    if key_path.exists() and cert_path.exists():
        serial = format(x509.load_der_x509_certificate(cert_path.read_bytes()).serial_number, "X").lstrip("0")
        for c in asc.call("GET", "/v1/certificates?filter[certificateType]=IOS_DEVELOPMENT&limit=200")["data"]:
            if c["attributes"].get("serialNumber", "").upper().lstrip("0") == serial:
                return c["id"]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "omarchy-apple-dev development")]))
           .sign(key, hashes.SHA256()))
    made = asc.call("POST", "/v1/certificates", {"data": {"type": "certificates", "attributes": {
        "certificateType": "IOS_DEVELOPMENT", "csrContent": csr.public_bytes(serialization.Encoding.PEM).decode(),
    }}})["data"]
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    der = base64.b64decode(made["attributes"]["certificateContent"])
    cert_path.write_bytes(der)
    (out / "cert.pem").write_bytes(x509.load_der_x509_certificate(der).public_bytes(serialization.Encoding.PEM))
    (out / "certificate-id").write_text(made["id"] + "\n")
    return made["id"]


def device(udid, name):
    found = asc.call("GET", f"/v1/devices?filter[udid]={udid}")["data"]
    if found:
        return found[0]["id"]
    return asc.call("POST", "/v1/devices", {"data": {"type": "devices", "attributes": {
        "name": name, "udid": udid, "platform": "IOS"}}})["data"]["id"]


def profile(bundle_id, cert_id, device_id, out):
    name = f"omarchy-apple-dev development {bundle_id}"
    for p in asc.call("GET", "/v1/profiles?filter[profileType]=IOS_APP_DEVELOPMENT&limit=200")["data"]:
        if p["attributes"]["name"] == name:
            asc.call("DELETE", f"/v1/profiles/{p['id']}")
    made = asc.call("POST", "/v1/profiles", {"data": {"type": "profiles",
        "attributes": {"name": name, "profileType": "IOS_APP_DEVELOPMENT"},
        "relationships": {
            "bundleId": asc.rel("bundleIds", asc.bundle_id(bundle_id)),
            "certificates": {"data": [{"type": "certificates", "id": cert_id}]},
            "devices": {"data": [{"type": "devices", "id": device_id}]},
        }}})["data"]
    path = out / f"{bundle_id}.mobileprovision"
    path.write_bytes(base64.b64decode(made["attributes"]["profileContent"]))
    return path, made["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle-id", required=True)
    ap.add_argument("--udid", required=True)
    ap.add_argument("--name", default="iPhone")
    ap.add_argument("--out", default=str(Path.home() / ".config/omarchy-apple-dev/development"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    cert_id = certificate(out)
    dev_id = device(a.udid, a.name)
    path, prof_id = profile(a.bundle_id, cert_id, dev_id, out)
    print(f"certificate {cert_id}, device {dev_id}, profile {prof_id} -> {path}")


if __name__ == "__main__":
    main()
