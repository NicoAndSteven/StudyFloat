"""检查本机浏览器中是否存在 B 站 Cookie，以及能否解密读取。"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

KEY_NAMES = {"SESSDATA", "bili_jct", "DedeUserID", "buvid3", "buvid4", "sid"}

browsers = {
    "Chrome": Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Default/Network/Cookies",
    "Edge": Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Edge/User Data/Default/Network/Cookies",
    "Firefox": None,
}
ff = Path(os.environ["APPDATA"]) / "Mozilla/Firefox/Profiles"
if ff.exists():
    for p in ff.glob("*"):
        if (p / "cookies.sqlite").exists():
            browsers["Firefox"] = p / "cookies.sqlite"
            break

for name, db in browsers.items():
    if db is None:
        print(f"{name}: 无 profile")
        continue
    try:
        tmp = Path(tempfile.gettempdir()) / f"sf_{name}_ck.sqlite"
        shutil.copy2(db, tmp)
        con = sqlite3.connect(tmp)
        if name == "Firefox":
            rows = con.execute(
                "select host, name from moz_cookies where host like '%bilibili%'"
            ).fetchall()
        else:
            rows = con.execute(
                "select host_key, name from cookies where host_key like '%bilibili%'"
            ).fetchall()
        keys = [r for r in rows if r[1] in KEY_NAMES]
        print(f"{name}: B站 cookie 共 {len(rows)} 条；关键登录 cookie {keys[:8]}")
        if name in ("Chrome", "Edge"):
            enc = con.execute(
                "select name, hex(substr(encrypted_value,1,3)) from cookies "
                "where host_key like '%bilibili.com' and name in ('SESSDATA','bili_jct')"
            ).fetchall()
            print(f"  加密值前缀(v10=DPAPI, v20=ABE): {enc}")
        con.close()
    except Exception as e:
        print(f"{name}: ERROR {e}")
