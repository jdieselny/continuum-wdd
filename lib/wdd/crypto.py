import os
import json
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

KEYS_DIR = "keys"
TRUST_STORE = os.path.join(KEYS_DIR, "trusted.json")

def generate_keys():
    print("Generating Ed25519 keypair...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    os.makedirs(KEYS_DIR, exist_ok=True)
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    priv_path = os.path.join(KEYS_DIR, "agent_private.pem")
    pub_path = os.path.join(KEYS_DIR, "agent_public.pem")
    
    with open(priv_path, "wb") as f:
        f.write(private_pem)
        
    with open(pub_path, "wb") as f:
        f.write(public_pem)
        
    print(f"Saved private key to {priv_path}")
    print(f"Saved public key to {pub_path}")
    
    # Update trust store
    trust_data = {}
    if os.path.exists(TRUST_STORE):
        with open(TRUST_STORE, "r") as f:
            try:
                trust_data = json.load(f)
            except json.JSONDecodeError:
                pass
                
    trust_data["agent_key"] = public_pem.decode("utf-8")
    
    with open(TRUST_STORE, "w") as f:
        json.dump(trust_data, f, indent=2)
        
    print(f"Updated trust store at {TRUST_STORE}")

if __name__ == "__main__":
    generate_keys()

