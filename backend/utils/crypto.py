"""
Encryption utilities for sensitive data
"""

import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Global encryption key - initialized once
_encryption_key = None


def _get_encryption_key() -> Fernet:
    """Get or create encryption key"""
    global _encryption_key
    
    if _encryption_key is None:
        settings = get_settings()
        
        # Derive key from secret key
        password = settings.secret_key.encode()
        salt = b'nexus_salt_change_in_production'  # In production, use random salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        _encryption_key = Fernet(key)
    
    return _encryption_key


def encrypt_password(password: str) -> str:
    """Encrypt a password or sensitive string"""
    try:
        fernet = _get_encryption_key()
        encrypted = fernet.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt a password or sensitive string"""
    try:
        fernet = _get_encryption_key()
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def generate_key() -> str:
    """Generate a new encryption key (for initial setup)"""
    return Fernet.generate_key().decode()