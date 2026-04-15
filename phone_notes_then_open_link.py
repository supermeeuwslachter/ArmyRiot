import random
import subprocess
import time
import os
from typing import Iterable, Optional

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

# ===== Config =====
PHONE_ID = "192.168.0.106:39335"  # Active wireless adb endpoint
APPIUM_SERVER = "http://127.0.0.1:4723"
PHONE_PIN = "11554422"  # Change if your unlock PIN changes
ADB_CONNECT_RETRIES = 3
ADB_CONNECT_RETRY_SLEEP_S = 1.5

# Text to type in the new note.
NOTE_TEXT = (
    "Live test note from automation.\n"
    "Typing should look human, not robotic.\n"
    "If you read this, the flow worked."
)

TARGET_URL = "https://supermeeuwslachter.github.io/ArmyRiot/"

# App mode: "voice_recorder" or "notes"
APP_MODE = "voice_recorder"

# Order matters: first available app is used.
APP_CANDIDATES = [
    "com.sec.android.app.voicenote",  # Samsung Voice Recorder
    "com.google.android.soundrecorder",
    "com.miui.soundrecorder",
    "com.coloros.soundrecorder",
    "com.simplemobiletools.voicerecorder",
    "org.fossify.voicerecorder",
]

TYPE_DELAY_MIN = 0.05
TYPE_DELAY_MAX = 0.18

# Resolved at runtime; defaults to configured PHONE_ID.
ACTIVE_DEVICE_ID = PHONE_ID


def list_installed_packages() -> list[str]:
    """Return installed package names on the active device."""
    result = run_adb("shell", "pm", "list", "packages")
    packages = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.split("package:", 1)[1].strip())
    return packages


def resolve_notes_package(candidates: Iterable[str]) -> Optional[str]:
    """Resolve the most likely target package installed on device.

    Priority:
    1) NOTE_APP_PACKAGE env var (exact package)
    2) explicit candidate list order
    3) fuzzy package match containing 'note'/'notes', preferring simple/fossify
    """
    env_override = (os.getenv("NOTE_APP_PACKAGE") or "").strip()
    installed = list_installed_packages()
    installed_set = set(installed)

    if env_override:
        if env_override in installed_set:
            print(f"[i] Using NOTE_APP_PACKAGE override: {env_override}")
            return env_override
        print(f"[!] NOTE_APP_PACKAGE '{env_override}' not installed; falling back to auto-detect")

    for package in candidates:
        if package in installed_set:
            return package

    # Fuzzy fallback for unknown app package variants.
    if APP_MODE == "voice_recorder":
        include_tokens = ("voice", "record", "recorder", "audio", "sound")
        fuzzy = [p for p in installed if any(tok in p.lower() for tok in include_tokens)]
    else:
        exclude_tokens = ("voice", "record", "recorder", "audio", "sound")
        fuzzy = [
            p for p in installed
            if ("note" in p.lower() or "notes" in p.lower())
            and not any(tok in p.lower() for tok in exclude_tokens)
        ]
    if not fuzzy:
        return None

    def rank_key(pkg: str) -> tuple[int, int, str]:
        low = pkg.lower()
        preferred = 0 if ("simple" in low or "fossify" in low) else 1
        # shorter package names are often the base app package over helpers
        return (preferred, len(pkg), pkg)

    fuzzy.sort(key=rank_key)
    chosen = fuzzy[0]
    print(f"[i] Auto-detected notes package by fuzzy match: {chosen}")
    return chosen


def run_adb(*args: str, device_id: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run an adb command, optionally targeting a specific device id."""
    target = device_id if device_id is not None else ACTIVE_DEVICE_ID
    cmd = ["adb"]
    if target:
        cmd.extend(["-s", target])
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def list_connected_devices() -> list[str]:
    """Return connected/online adb device ids."""
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=False)
    devices = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def ensure_adb_connection() -> str:
    global ACTIVE_DEVICE_ID
    print("[*] Ensuring adb connection...")

    # 1) If configured id is already connected, use it directly.
    connected = list_connected_devices()
    if PHONE_ID in connected:
        ACTIVE_DEVICE_ID = PHONE_ID
        print(f"[OK] adb connected on configured device: {ACTIVE_DEVICE_ID}")
        return ACTIVE_DEVICE_ID

    # 2) Retry wireless connect on configured id.
    for attempt in range(1, ADB_CONNECT_RETRIES + 1):
        result = subprocess.run(["adb", "connect", PHONE_ID], capture_output=True, text=True, check=False)
        msg = ((result.stdout or "") + " " + (result.stderr or "")).strip()
        print(f"[i] adb connect attempt {attempt}/{ADB_CONNECT_RETRIES}: {msg}")
        time.sleep(ADB_CONNECT_RETRY_SLEEP_S)

        connected = list_connected_devices()
        if PHONE_ID in connected:
            ACTIVE_DEVICE_ID = PHONE_ID
            print(f"[OK] adb connected on configured device: {ACTIVE_DEVICE_ID}")
            return ACTIVE_DEVICE_ID

    # 3) Fallback: if another device is connected (e.g., USB), use it.
    connected = list_connected_devices()
    if connected:
        ACTIVE_DEVICE_ID = connected[0]
        print(
            f"[!] Configured device '{PHONE_ID}' not available. "
            f"Falling back to connected device '{ACTIVE_DEVICE_ID}'."
        )
        return ACTIVE_DEVICE_ID

    raise RuntimeError(
        "No adb devices available. Ensure your phone is connected via USB or wireless adb. "
        f"Configured device: '{PHONE_ID}'."
    )


def build_driver(device_id: str) -> webdriver.Remote:
    print("[*] Connecting to Appium...")
    options = UiAutomator2Options()
    options.device_name = device_id
    options.udid = device_id
    options.new_command_timeout = 300
    options.adb_exec_timeout = 60000
    options.skip_unlock = True
    driver = webdriver.Remote(APPIUM_SERVER, options=options)
    print("[OK] Appium connected")
    return driver


def unlock_phone(driver: webdriver.Remote, pin: str) -> None:
    print("[*] Unlocking phone...")

    # Wake screen (KEYCODE_WAKEUP = 224), then swipe up.
    try:
        driver.press_keycode(224)
    except Exception:
        # Fallback power toggle if wakeup is not accepted.
        driver.press_keycode(26)

    time.sleep(0.5)
    driver.swipe(540, 1800, 540, 400, duration=800)
    time.sleep(0.6)

    # Android keycodes for digits 0-9 are 7-16.
    digit_keycodes = {str(i): 7 + i for i in range(10)}
    for ch in pin:
        if ch not in digit_keycodes:
            continue
        driver.press_keycode(digit_keycodes[ch])
        time.sleep(0.08)

    # Press Enter to submit PIN.
    driver.press_keycode(66)
    time.sleep(1.0)
    print("[OK] Unlock sequence sent")


def activate_first_available_notes_app(driver: webdriver.Remote, packages: Iterable[str]) -> str:
    print(f"[*] Opening app for mode '{APP_MODE}'...")
    resolved = resolve_notes_package(packages)
    if resolved:
        try:
            driver.activate_app(resolved)
            time.sleep(1.2)
            print(f"[OK] Opened app: {resolved}")
            return resolved
        except WebDriverException:
            print(f"[!] Failed to activate resolved package '{resolved}', trying fallback list...")

    installed = set(list_installed_packages())
    for package in packages:
        if package not in installed:
            continue
        try:
            driver.activate_app(package)
            time.sleep(1.2)
            print(f"[OK] Opened app (fallback): {package}")
            return package
        except WebDriverException:
            pass

    raise RuntimeError("No supported target app found. Update APP_CANDIDATES for your phone.")


def click_first_if_exists(driver: webdriver.Remote, xpaths: Iterable[str], timeout_s: float = 1.2) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for xpath in xpaths:
            els = driver.find_elements(By.XPATH, xpath)
            if els:
                try:
                    els[0].click()
                    time.sleep(0.6)
                    return True
                except Exception:
                    pass
        time.sleep(0.2)
    return False


def open_new_note_if_needed(driver: webdriver.Remote) -> None:
    print("[*] Attempting to open a new note...")
    selectors = [
        "//*[@content-desc='Nieuwe notitie']",
        "//*[@content-desc='Nieuwe notitie maken']",
        "//*[@content-desc='Notitie maken']",
        "//*[@content-desc='New note']",
        "//*[@content-desc='Create note']",
        "//*[contains(@resource-id,'fab')]",
        "//*[@text='Nieuwe notitie']",
        "//*[@text='Notitie maken']",
        "//*[@text='New note']",
        "//*[@text='Create note']",
        "//*[@text='+']",
    ]
    if click_first_if_exists(driver, selectors, timeout_s=2.0):
        print("[OK] New note opened")
    else:
        print("[i] New-note button not found; continuing (may already be in editor)")


def open_lijst_if_present(driver: webdriver.Remote) -> None:
    print("[*] Attempting to open 'Lijst'...")
    selectors = [
        "//*[@text='Lijst']",
        "//*[@content-desc='Lijst']",
        "//*[@text='List']",
        "//*[@content-desc='List']",
    ]
    if click_first_if_exists(driver, selectors, timeout_s=2.5):
        print("[OK] Opened 'Lijst'")
    else:
        print("[i] 'Lijst' button not found")


def find_editor(driver: webdriver.Remote):
    editors = driver.find_elements(By.XPATH, "//android.widget.EditText")
    if editors:
        return editors[0]

    # Fallback: tap center and retry.
    size = driver.get_window_size()
    driver.tap([(size["width"] // 2, size["height"] // 2)])
    time.sleep(0.5)
    editors = driver.find_elements(By.XPATH, "//android.widget.EditText")
    if not editors:
        raise RuntimeError("No editable text field found in notes app.")
    return editors[0]


def type_human_like(element, text: str) -> None:
    print("[*] Typing note text human-like...")
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(TYPE_DELAY_MIN, TYPE_DELAY_MAX))
    print("[OK] Finished typing")


def open_target_url() -> None:
    print(f"[*] Opening URL: {TARGET_URL}")
    result = run_adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", TARGET_URL)
    if result.returncode != 0:
        raise RuntimeError(f"Could not open URL. stderr: {result.stderr.strip()}")
    print("[OK] URL opened")


def main() -> None:
    driver: Optional[webdriver.Remote] = None
    try:
        device_id = ensure_adb_connection()
        driver = build_driver(device_id)

        unlock_phone(driver, PHONE_PIN)
        opened_app = activate_first_available_notes_app(driver, APP_CANDIDATES)
        open_lijst_if_present(driver)
        print(f"[OK] Voice recorder opened ({opened_app}) and attempted 'Lijst' click.")

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
