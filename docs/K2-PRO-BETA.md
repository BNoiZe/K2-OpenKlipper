# K2 Pro (F012): first run, step by step (BETA)

The K2 Pro config is built from Creality's own K2 Pro 1.1.7.0 configuration
(board CR0CN200400C10, structure_version 0, K2 Pro Combo with one CFS). It
has not completed a supervised first run yet, so the installer still asks
for `OKL_FORCE=1`. This guide checks each part on its own before anything
prints. Stay next to the printer with the power switch in reach, and after
any problem power-cycle instead of restarting Klipper.

Uninstalling puts the printer back to stock at any point:

    sh /mnt/UDISK/k2-mainline-20260729-v62/uninstall.sh && reboot

## What is different from the K2

The K2 Pro is a K2 with a bigger frame and the K2 Plus chamber heater: one
geared Z motor (TMC2208), one bottom switch (PA15), the same motor-bus
addresses and the same fans.

| | K2 | K2 Pro |
|---|---|---|
| Travel | X 262, Y -3 to 296.5, Z 270 | X 302, Y -6.5 to 332, Z 303 |
| Z speed | 20 mm/s, accel 500 | 10 mm/s, accel 300 (stock) |
| Nozzle thermistor | 260k / 738 / 98 ohm | 98.6k / 377 / 73 ohm (stock `my_thermistor`) |
| Nozzle PID | tuned K2 | stock K2 Pro 26.861 / 3.035 / 59.429 |
| Bed heater | half power, 110/220 V sets | full power, one PID (37 / 0.18 / 280), max 120 C |
| Chamber heater | none | PTC on PC12, fan PB14/PB2, tach PC6 (as K2 Plus) |
| Belt tensioners | none | `[belt_mdl]` modules (as K2 Plus) |
| Mesh | 7x7 over 255 mm | 9x9 over 290 mm |
| Chute, brush, cutter, strip | K2 positions | stock K2 Pro `box.cfg` / `prtouch_v3` positions |

The config is generated from the K2 one by `tools/k2pro/make_k2pro_cfg.py`
(every change is listed there with its source).

## Known gaps

- **Bottom switch height** is `position_endstop: 296`, a deliberately low
  guess (stock formula gives 301; the K2 measured about 5 mm under its stock
  value). Too low is safe: the tap fails instead of touching. Step 5
  measures it; the first `G28` with Z may fail its tap until then.
- **Cutter ram distance** is the K2's `cutter_cut_x: -7.2`. Stock calibrated
  -8.4 on the test printer (range -6.5 to -10). Check the cut in step 8.
- **First-layer correction** keeps the K2 default 0.04 mm: Creality's K2 Pro
  coefficients give the same 0.040 mm at 220 C (tap at 140 C).
- Untested: everything. Positions come from the stock config, not from a
  run.

## Before you start

1. Creality firmware 1.1.7.0, root on, SSH in as root.
2. Empty bed, nothing in the chute area, filament unloaded.

## Step 1: check, then install

    OKL_FORCE=1 OKL_REF=<branch> sh /tmp/install.sh --check
    OKL_FORCE=1 OKL_REF=<branch> sh /tmp/install.sh

The check must print `K2 Pro board: CR0CN200400C10   structure_version: 0`.
Then in the Mainsail console (`http://PRINTER-IP:4409/`):

    MOTOR_FAULTS
    MOTOR_E_ADDR
    KZ_ALIGN_STATUS

`MOTOR_FAULTS` should list X, Y and E with no errors; `KZ_ALIGN_STATUS`
should show PA15 TRIGGERED with the bed all the way down.

## Step 2: heaters and fans (no motion)

    M140 S50
    M104 S150

Both temperatures should rise steadily and read room temperature before.
**If the nozzle reads wildly off room temperature, stop: the thermistor
table is wrong.** Then `M104 S0`, `M140 S0`, `M106 S128`, `M107`.

## Step 3: home X and Y

Hand on the power switch, one axis at a time:

    G28 Y
    G28 X

## Step 4: position check (X and Y only, slow)

    CHUTE_POSITION_CHECK

Visits each chute, brush, strip and cutter position at 20 mm/s and names
every stop. Nothing extrudes, wipes or cuts. Note any stop that is off.

## Step 5: Z and the bottom switch

    KZ_ALIGN_MEASURE CONFIRM=1

Put the suggested value in printer-overrides.cfg, save and restart:

    [k2_z_align]
    position_endstop: 301.00

Then `G28` and `BED_MESH_CALIBRATE`.

## Step 6: chamber heater

Door shut, nothing printing:

    CHAMBER_HEAT TARGET=45
    CHAMBER_STATUS

`fan tach` must be above 0 while it heats. `CHAMBER_HEAT TARGET=0` to stop.
To turn it off: `[hark_chamber]` `enable: False` in printer-overrides.cfg.

## Step 7: belt tension (read only)

    BELT_TENSION_STATUS

Send the output. Do not run `BELT_TENSION CONFIRM=1` before it is reviewed.

## Step 8: CFS load, cut, unload

One slot, PLA. Load, unload and a cut, watching the cutter and the chute.

## Step 9: prints

A small PLA print in the middle, then a large one (close to 300 mm), then a
multi-slot print. In OrcaSlicer import `orca/Creality K2 Pro OpenKlipper.json`
and set your printer's IP.

## What to send back after each step

The console output, `klippy.log` after any problem (remove serial numbers,
tokens, Wi-Fi and private IPs), and photos or a video where something moved.
