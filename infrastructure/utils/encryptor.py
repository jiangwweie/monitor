"""
简单加解密工具类
用于数据库中敏感字段（如 API Secret）的简单单向加扰保护。
防止明文泄露。
"""
import base64
import os

# 本地环境变量，如未设置则使用固定值
SECRET_XOR_KEY = os.getenv("CRYPTO_RADAR_XOR_KEY", "apple_design_secret_2026")

def simple_encrypt(plain_text: str) -> str:
    """简单的异或混淆配合 Base64，非绝对安全，但能规避明文存储"""
    if not plain_text:
        return ""
    encoded = []
    for i, c in enumerate(plain_text):
        key_c = SECRET_XOR_KEY[i % len(SECRET_XOR_KEY)]
        encoded.append(chr(ord(c) ^ ord(key_c)))
    
    # 编码成 Base64 字符串
    return base64.b64encode("".join(encoded).encode('utf-8')).decode('utf-8')

def simple_decrypt(cipher_text: str) -> str:
    """解混淆"""
    if not cipher_text:
        return ""
    try:
        decoded_b64 = base64.b64decode(cipher_text.encode('utf-8')).decode('utf-8')
        decoded = []
        for i, c in enumerate(decoded_b64):
            key_c = SECRET_XOR_KEY[i % len(SECRET_XOR_KEY)]
            decoded.append(chr(ord(c) ^ ord(key_c)))
        return "".join(decoded)
    except Exception:
        return ""
