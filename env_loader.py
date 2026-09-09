"""
Roktandrazo Outreach - Environment Loader
从 .env 文件加载配置，不硬编码任何敏感信息
"""

import os

if os.path.exists(os.path.join(os.path.dirname(__file__), ".development-copy")):
    from development_safety import install as _install_development_safety
    _install_development_safety()

def _load_env():
    """Load .env file from project root"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f".env file not found at {env_path}")
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if value.startswith('__'):
                    continue
                dev_copy = os.path.exists(os.path.join(os.path.dirname(__file__), ".development-copy"))
                if dev_copy:
                    # Never inherit production credentials into this copy.
                    os.environ[key] = value
                elif value:
                    os.environ.setdefault(key, value)

_load_env()


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_smtp_config() -> dict:
    return {
        "host": get_env("BD_SMTP_HOST", "smtp.exmail.qq.com"),
        "port": int(get_env("BD_SMTP_PORT", "465")),
        "use_ssl": get_env("BD_SMTP_SSL", "true").lower() == "true",
        "user": get_env("BD_SMTP_USER"),
        "password": get_env("BD_SMTP_PASS"),
    }


def get_sender_info() -> dict:
    return {
        "name": get_env("BD_FROM_NAME", "Ian"),
        "email": get_env("BD_FROM_EMAIL"),
    }


def get_imap_config() -> dict:
    return {
        "host": get_env("BD_IMAP_HOST", "imap.exmail.qq.com"),
        "port": int(get_env("BD_IMAP_PORT", "993")),
        "use_ssl": get_env("BD_IMAP_SSL", "true").lower() == "true",
        "user": get_env("BD_IMAP_USER"),
        "password": get_env("BD_IMAP_PASS"),
    }


def get_sending_limits() -> dict:
    return {
        "max_per_batch": int(get_env("BD_MAX_PER_BATCH", "5")),
        "max_per_day": int(get_env("BD_MAX_PER_DAY", "30")),
        "delay_seconds": int(get_env("BD_DELAY_SECONDS", "60")),
    }


def get_test_config() -> dict:
    return {
        "test_mode": get_env("BD_TEST_MODE", "true").lower() == "true",
        "test_email": get_env("BD_TEST_EMAIL"),
    }


def is_configured() -> bool:
    """Check if minimum required config is set"""
    cfg = get_smtp_config()
    sender = get_sender_info()
    return bool(cfg["user"] and cfg["password"] and sender["email"])


def mask(value: str) -> str:
    """Mask sensitive value for safe display"""
    if not value or len(value) < 4:
        return "***"
    return value[:2] + "***" + value[-2:]
