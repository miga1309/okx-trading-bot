# patch_v022_disable_illiquid_ban.py
# Для текущего main_v022.py
#
# Что делает:
# 1) Убирает пропуск инструментов по illiquid/temp ban в scan_markets()
# 2) Убирает накопление illiquid-банов в evaluate_entry()
# 3) Оставляет саму проверку ликвидности: если рынок неликвидный, вход просто пропускается без бана
#
# Использование:
#   python patch_v022_disable_illiquid_ban.py

from pathlib import Path
import shutil
import sys

TARGET_FILE = Path("main_v022.py")
BACKUP_FILE = Path("main_v022.py.bak_disable_illiquid_ban")


def fail(msg: str) -> None:
    print(f"ОШИБКА: {msg}")
    sys.exit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET_FILE.exists():
        fail(f"Файл не найден: {TARGET_FILE.resolve()}")

    text = TARGET_FILE.read_text(encoding="utf-8")

    old_scan_markets = '''
    def scan_markets(self) -> None:
        for inst_id in self.gateway.swap_ids:
            if not self.running:
                break
            blocked_until = self.temp_blocked_until.get(inst_id, 0.0)
            if blocked_until and blocked_until > time.time():
                continue
            illiquid_until = self.illiquid_instruments.get(inst_id, 0.0)
            if illiquid_until and illiquid_until > time.time():
                continue
            if inst_id in self.cfg.blacklist or inst_id in self.blocked_instruments or is_hidden_instrument(inst_id):
                continue
            if inst_id in self.position_state:
                continue
            try:
                self.evaluate_entry(inst_id)
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка анализа входа: {exc}")
                logging.warning("Entry eval failed for %s: %s", inst_id, exc)
'''.strip("\n")

    new_scan_markets = '''
    def scan_markets(self) -> None:
        for inst_id in self.gateway.swap_ids:
            if not self.running:
                break
            if inst_id in self.cfg.blacklist or inst_id in self.blocked_instruments or is_hidden_instrument(inst_id):
                continue
            if inst_id in self.position_state:
                continue
            try:
                self.evaluate_entry(inst_id)
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка анализа входа: {exc}")
                logging.warning("Entry eval failed for %s: %s", inst_id, exc)
'''.strip("\n")

    old_liquidity_block = '''
        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            should_ban, final_reason = self._register_illiquid_rejection(inst_id, liquid_reason)
            if should_ban:
                self._block_illiquid_instrument(inst_id, final_reason)
                logging.info("%s: пропуск входа, illiquidity-filter -> ban (%s)", inst_id, final_reason)
            else:
                logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, final_reason)
            return
'''.strip("\n")

    new_liquidity_block = '''
        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            logging.info("%s: пропуск входа, illiquidity-filter без бана (%s)", inst_id, liquid_reason)
            return
'''.strip("\n")

    text = replace_once(text, old_scan_markets, new_scan_markets, "scan_markets")
    text = replace_once(text, old_liquidity_block, new_liquidity_block, "evaluate_entry_liquidity_block")

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:  {BACKUP_FILE.resolve()}")
    print(f"Updated: {TARGET_FILE.resolve()}")


if __name__ == "__main__":
    main()