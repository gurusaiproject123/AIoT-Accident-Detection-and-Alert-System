# Simple local car controls

These headers adapt the supplied working five-button page to the combined
ESP32 diagnostics firmware. The complete sketch is packaged locally as
`C:\Users\THINKPAD\Downloads\AIoTCarSimple\AIoTCarSimple.ino`.
Open that sketch, rather than uploading the standalone motor-only example.
The package includes the existing private config and supporting headers;
credentials are not copied into this repository.

- Connect the phone to the car Wi-Fi and open `http://192.168.4.1`.
- The existing local driver login remains. There is no Acquire button.
- Hold Forward, Reverse, Left, or Right. Release or press STOP to stop.
- Commands repeat every 150 ms. The independent motor task stops after
  600 ms without a fresh command, or when the phone disconnects.
- Left stops the left motor; Right stops the right motor.
- Output is full duty (255), matching the supplied standalone sketch.
- Physical button and incident-window interlocks still prevent driving.
- Sensor reporting and bounded simulated location remain in the main sketch.

Test with wheels raised: hold and release each direction, press STOP, then
disconnect the phone while holding a direction and verify the motors stop.
Compilation does not verify motor wiring or stopping on the actual hardware.
