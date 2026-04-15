# Repair Phone Connection After Reboot

Use this guide when the automation script stops working after your Android phone has been powered off and on again.

## Why this happens
After a reboot, Android wireless debugging often changes the active debug port or drops the trusted pairing session. The saved endpoint in your script may no longer be valid.

## Quick recovery checklist
1. Make sure phone and PC are on the same Wi-Fi network.
2. On phone, open:
   - Settings -> Ontwikkelaarsopties
   - Enable draadloze foutopsporing
3. On phone, tap Apparaat koppelen met koppelingscode.
4. In PowerShell on your PC, run:
   adb pair PHONE_IP:PAIR_PORT
5. Enter the 6-digit pairing code from the phone.
6. Still in PowerShell, run:
   adb connect PHONE_IP:DEBUG_PORT
7. Verify the connection:
   adb devices
8. You should see one device line ending with status "device".

## If connect fails
- Error 10061 or "connection refused": the debug port changed. Repeat pairing and use the new port from the phone screen.
- No devices listed: re-open Wireless debugging screen and retry pair + connect.
- Still failing: toggle Wireless debugging off/on and retry.

## Update this project after reconnecting
This project has two scripts with phone endpoint defaults.
Update both so they match the new PHONE_IP:DEBUG_PORT.

1. phone_notes_then_open_link.py
   - Update PHONE_ID value near the top of the file.
2. ui_phone_challenge.py
   - Update default PHONE_ID inside os.getenv(...).

## Validation steps
1. Start Appium server:
   appium.cmd in powershell
2. Confirm ADB sees the phone:
   adb devices
3. Run the script:
   python phone_notes_then_open_link.py

If step 2 does not show your phone as "device", the script will not work yet.

## Optional improvement
To avoid editing files after each reboot, switch phone_notes_then_open_link.py to read PHONE_ID from an environment variable (same style as ui_phone_challenge.py).
