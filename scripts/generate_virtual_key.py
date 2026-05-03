"""Generate a Tesla Virtual Key pair (EC P-256).

Output:
    <DATA_DIR>/tesla_keys/private.pem
        — private key, must NEVER be committed or shared
    ./public/.well-known/appspecific/com.tesla.3p.public-key.pem
        — public key, must be served at:
        https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem

Tesla spec: curve must be prime256v1 (NIST P-256 / secp256r1), PEM format.

Run once. If keys already exist, the script refuses to overwrite them
(to prevent accidentally invalidating Virtual Key pairings on vehicles).
"""
from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from tesla_skill.config import settings


def main() -> None:
    private_path = Path(settings.tesla_private_key_path)
    # Public key: relative to repo root, so user can copy/symlink to webroot
    public_path = Path("public/.well-known/appspecific/com.tesla.3p.public-key.pem").resolve()

    if private_path.exists() or public_path.exists():
        print("ERROR: key files already exist:", file=sys.stderr)
        print(f"  private: {private_path}", file=sys.stderr)
        print(f"  public:  {public_path}", file=sys.stderr)
        print("Delete them manually if you really want to regenerate.", file=sys.stderr)
        print("Note: regenerating means re-pairing the Virtual Key with your vehicle.", file=sys.stderr)
        sys.exit(1)

    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    private_path.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)

    public_path.write_bytes(
        public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print(f"✅ Private key: {private_path}  (chmod 600)")
    print(f"✅ Public key:  {public_path}")
    print()
    print("Next steps:")
    print("  1. Upload the *public* key to your web server so this returns 200:")
    print("       https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem")
    print("     Verify:")
    print("       curl -I https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem")
    print()
    print("  2. Run: python scripts/register_partner.py")
    print("     (This registers your domain + public key with Tesla so OAuth works.)")
    print()
    print("  3. Pair the Virtual Key with your vehicle via the Tesla mobile app:")
    print("       Phone browser → https://tesla.com/_ak/<your-domain>")
    print("       (or https://www.tesla.cn/_ak/<your-domain> for China-region cars)")
    print()
    print("Keep the private key secret. It's used by tesla-control to sign control commands.")


if __name__ == "__main__":
    main()
