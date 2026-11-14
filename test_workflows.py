import os, tempfile
from cryptography.fernet import Fernet
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp(prefix='kfd-test-'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-that-is-long-enough-for-hs256-123456')
os.environ.setdefault('ENCRYPTION_KEY', Fernet.generate_key().decode())
os.environ.setdefault('INITIAL_ADMIN_USERNAME', 'admin')
os.environ.setdefault('INITIAL_ADMIN_PASSWORD', 'Admin-Test-Password-2026!')
