"""口令哈希与会话令牌工具。

口令用 PBKDF2-HMAC-SHA256（标准库 hashlib，避免引入 passlib/bcrypt 等新依赖），
每个用户独立随机盐；存储格式：pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>。
"""
import base64
import hashlib
import hmac
import secrets

# PBKDF2 迭代次数：100k 在当前硬件下约几十毫秒，足够慢且不拖慢登录体验
_PBKDF2_ITERATIONS = 100_000
_SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """生成口令哈希（带随机盐）。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    """校验口令：constant-time 比较防时序攻击；格式非法一律返回 False。"""
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """生成 URL 安全的随机会话令牌。"""
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)
