"""
Camada de save: decripta/encripta o SaveFile .es3 (Easy Save 3, AES-128-CBC),
des-aninha os JSON internos (Account/Player) e recalcula o SystemInfo (HMAC de
integridade) ao salvar. Zero dependencias obrigatorias (usa 'cryptography' se
houver, senao o AES puro embutido).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
from hashlib import pbkdf2_hmac

# --- chaves/constantes (extraidas da 1.00.17; conferidas da 1.00.11 a 1.2.8) ---
ES3_PASSWORD = "emuMqG3bLYJ938ZDCfieWJ"          # senha de criptografia do Easy Save 3
PBKDF2_ITERS = 100
KEY_SIZE = 16
IV_SIZE = 16
# Chave do HMAC-SHA256 de integridade (campo "SystemInfo"); extraida em runtime e validada.
SYSTEMINFO_HMAC_KEY = bytes.fromhex(
    "93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456"
)
SYSTEMINFO_SEP = "|"

# --- AES-CBC: usa 'cryptography' (rapido) se disponivel, senao AES puro ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def _aes_cbc_decrypt(key, iv, data):
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return d.update(data) + d.finalize()

    def _aes_cbc_encrypt(key, iv, data):
        e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return e.update(data) + e.finalize()

    AES_BACKEND = "cryptography"
except Exception:
    from . import aes_pure

    def _aes_cbc_decrypt(key, iv, data):
        return aes_pure.cbc_decrypt(key, iv, data)

    def _aes_cbc_encrypt(key, iv, data):
        return aes_pure.cbc_encrypt(key, iv, data)

    AES_BACKEND = "pure-python"


def _pkcs7_pad(data, block=16):
    n = block - (len(data) % block)
    return data + bytes([n]) * n


def _pkcs7_unpad(data):
    n = data[-1]
    if n < 1 or n > 16:
        raise ValueError("padding PKCS7 invalido")
    return data[:-n]


def _derive_key(password, iv):
    return pbkdf2_hmac("sha1", password.encode("utf-8"), iv, PBKDF2_ITERS, dklen=KEY_SIZE)


def es3_decrypt(raw, password=ES3_PASSWORD):
    iv, ct = raw[:IV_SIZE], raw[IV_SIZE:]
    key = _derive_key(password, iv)
    return _pkcs7_unpad(_aes_cbc_decrypt(key, iv, ct))


def es3_encrypt(plaintext, password=ES3_PASSWORD, iv=None):
    if iv is None:
        iv = secrets.token_bytes(IV_SIZE)
    key = _derive_key(password, iv)
    return iv + _aes_cbc_encrypt(key, iv, _pkcs7_pad(plaintext))


def systeminfo_for(account_str, player_str, steam_id):
    """Base64(HMAC-SHA256(chave, account|player|steamId)) sobre as strings exatas gravadas."""
    msg = SYSTEMINFO_SEP.join([account_str, player_str, str(steam_id)]).encode("utf-8")
    return base64.b64encode(hmac.new(SYSTEMINFO_HMAC_KEY, msg, hashlib.sha256).digest()).decode("ascii")


def write_atomic(path, data, backup=False):
    """Escreve <path>.tmp, guarda o atual em <path>.bak (se backup) e troca com os.replace:
    o arquivo nunca fica pela metade."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    if backup and os.path.exists(path):
        shutil.copyfile(path, path + ".bak")
    os.replace(tmp, path)


class SaveFile:
    """Save carregado e des-aninhado. `account` e `player` sao dicts editaveis."""

    def __init__(self, es3_obj, password=ES3_PASSWORD):
        self._es3 = es3_obj           # estrutura ES3 externa {key: {__type, value}}
        self.password = password
        self.account = json.loads(es3_obj["AccountSaveData"]["value"])
        self.player = json.loads(es3_obj["PlayerSaveData"]["value"])

    @classmethod
    def load(cls, path, password=ES3_PASSWORD):
        with open(path, "rb") as fh:
            return cls.from_bytes(fh.read(), password)

    @classmethod
    def from_bytes(cls, raw, password=ES3_PASSWORD):
        es3_obj = json.loads(es3_decrypt(raw, password).decode("utf-8"))
        return cls(es3_obj, password)

    def systeminfo_ok(self):
        """O SystemInfo do arquivo confere com as strings dele (o jogo exige isso no load)."""
        e = self._es3
        try:
            return e["SystemInfo"]["value"] == systeminfo_for(
                e["AccountSaveData"]["value"], e["PlayerSaveData"]["value"], self.account.get("ownerSteamId", ""))
        except (KeyError, TypeError):
            return False

    def _serialize_inner(self, obj):
        # compacto, UTF-8 cru — igual ao Newtonsoft (semanticamente equivalente)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    def to_es3_bytes(self):
        acc = self._serialize_inner(self.account)
        ply = self._serialize_inner(self.player)
        sysinfo = systeminfo_for(acc, ply, self.account.get("ownerSteamId", ""))
        self._es3["AccountSaveData"]["value"] = acc
        self._es3["PlayerSaveData"]["value"] = ply
        self._es3["SystemInfo"]["value"] = sysinfo
        text = json.dumps(self._es3, ensure_ascii=False, indent="\t")
        return es3_encrypt(text.encode("utf-8"), self.password)

    def save(self, path, backup=True):
        """Grava atomicamente: escreve <path>.tmp, guarda o atual em <path>.bak e troca com
        os.replace (o arquivo nunca fica pela metade). Devolve os bytes gravados."""
        blob = self.to_es3_bytes()
        write_atomic(path, blob, backup)
        return blob
