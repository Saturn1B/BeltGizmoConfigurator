import customtkinter as ctk
import serial
from serial.tools import list_ports
from tkinter import StringVar
import tkinter as tk
import time
import os
from PIL import Image

# =====================================================
# APPEARANCE
# =====================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# =====================================================
# SPENGLER SYSTEMS — INDUSTRIAL TERMINAL THEME
# =====================================================

# Structure / Backgrounds
S_BG          = "#0c0d0e"   # Industrial steel black
S_PANEL       = "#111416"   # Raised panel surface
S_PANEL2      = "#171b1e"   # Inner panel inset
S_BORDER      = "#2a2e32"   # Subtle panel border
S_BORDER2     = "#1e2225"   # Inner border / separator

# Primary Accent — Proton Beam Red (save, critical actions)
S_RED         = "#d62828"
S_RED_HOVER   = "#a81e1e"
S_RED_DIM     = "#2a0a0a"
S_RED_MID     = "#6b1414"

# Secondary Accent — Ecto-Plasm Yellow (toggles, selection, highlights)
S_YELLOW      = "#f7b731"
S_YELLOW_DIM  = "#3d2d0c"
S_YELLOW_MID  = "#7d5c18"

# VFD Display — phosphor glow
S_VFD_BG      = "#050e0d"
S_VFD_ON      = "#00ffdd"
S_VFD_DIM     = "#0a2e2a"

# Typography
S_TEXT        = "#b8bfc7"   # Primary readable text
S_TEXT_DIM    = "#4a5260"   # Muted label text
S_TEXT_BRIGHT = "#dce3ea"   # Bright headings

# Status lights
S_GREEN_ON    = "#39d353"
S_RED_ON      = "#d62828"
S_LIGHT_OFF   = "#1a1d20"

FONT_MONO     = "Courier New"

# =====================================================
# GLOBALS
# =====================================================

ser = None

SEGMENTS = {
    '0': "ABCDEF",
    '1': "BC",
    '2': "ABGED",
    '3': "ABCDG",
    '4': "FGBC",
    '5': "AFGCD",
    '6': "AFGCDE",
    '7': "ABC",
    '8': "ABCDEFG",
    '9': "ABCDFG",

    'A': "ABCEFG",
    'B': "CDEFG",
    'C': "ADEF",
    'D': "BCDEG",
    'E': "ADEFG",
    'F': "AEFG",
    'G': "ACDEF",
    'H': "BCEFG",
    'I': "BC",
    'J': "BCDE",
    'K': "EFG",
    'L': "DEF",
    'M': "ACEF",
    'N': "CEG",
    'O': "ABCDEF",
    'P': "ABEFG",
    'Q': "ABCFD",
    'R': "EG",
    'S': "AFGCD",
    'T': "DEFG",
    'U': "BCDEF",
    'V': "CDE",
    'W': "BDF",
    'X': "BCEFG",
    'Y': "BCDFG",
    'Z': "ABDEG",

    '-': "G",
    '_': "D",
    '=': "DG",
    ' ': "",
}

previewIndex = 0
lastPreviewScroll = 0

py_current_step = 0
py_step_start_time = 0
py_last_frame_time = 0
py_frame_index = 0
py_blink_state = False

last_active_display_mode = "simple"

# =====================================================
# DEFAULT DISPLAY SETTINGS
# =====================================================

DEFAULT_TEXT = "NO_GHOST"
DEFAULT_SPEED = 250
DEFAULT_SPACING = 8
DEFAULT_FORCE_SCROLL = False

# =====================================================
# SERIAL
# =====================================================

def get_ports():

    ports = [p.device for p in list_ports.comports()]

    if not ports:
        return ["No COM ports"]

    return ports

def connect_serial():

    global ser

    selected = portMenu.get()

    if selected == "No COM ports":

        statusLabel.configure(
            text="> NO ARDUINO DETECTED"
        )

        set_status_state("disconnected")

        return

    set_status_state("connecting")

    try:

        if ser is not None:

            try:
                ser.close()
            except:
                pass

        ser = serial.Serial(
            selected,
            115200,
            timeout=1
        )

        # DON'T BLOCK TKINTER
        app.after(2000, finish_connection, selected)

    except Exception:

        statusLabel.configure(
            text="> CONNECTION FAILED"
        )

        try:
            ser.close()
        except:
            pass

        ser = None

        set_controls_enabled(False)

        set_status_state("failed_connection")

def finish_connection(selected):

    global ser

    try:

        if ser is None or not ser.is_open:
            raise Exception("Port failed")

        statusLabel.configure(
            text=f"> CONNECTED: {selected}"
        )

        set_controls_enabled(True)

        set_status_state("connected_success")

        app.after(1000, load_config_from_arduino)

    except Exception:

        statusLabel.configure(
            text="> CONNECTION FAILED"
        )

        try:
            ser.close()
        except:
            pass

        ser = None

        set_controls_enabled(False)

        set_status_state("failed_connection")

def load_config_from_arduino():
    set_status_state("loading")
    global ser

    if ser is None:
        return

    try:
        ser.reset_input_buffer()
        ser.write("GETCONFIG\n".encode())
        config = {}
        start = time.time()

        while time.time() - start < 2:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key] = value
                elif line == "ENDCONFIG":
                    break

        # ==========================================
        # LOAD MAPPINGS
        # ==========================================
        ser.reset_input_buffer()
        ser.write("GETMAP\n".encode())
        segMap = []
        gridMap = []
        start = time.time()

        while time.time() - start < 2:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                if line.startswith("SEGMAP="):
                    segMap = [int(x) for x in line[7:].split(",")]
                elif line.startswith("GRIDMAP="):
                    gridMap = [int(x) for x in line[8:].split(",")]
                elif line == "ENDMAP":
                    break

        # ==========================================
        # APPLY SEGMENT MAPPINGS
        # ==========================================
        segmentNames = ["SEG_E", "SEG_D", "SEG_C", "SEG_DP", "SEG_A", "SEG_G", "SEG_F", "SEG_B"]
        for logicalIndex, outputPin in enumerate(segMap):
            pinName = f"OUT{outputPin}"
            if pinName in mappingVars:
                mappingVars[pinName].set(segmentNames[logicalIndex])

        # ==========================================
        # APPLY GRID MAPPINGS
        # ==========================================
        for gridIndex, outputPin in enumerate(gridMap):
            pinName = f"OUT{outputPin}"
            if pinName in mappingVars:
                mappingVars[pinName].set(f"GRID_{gridIndex + 1}")

        # ==========================================
        # RESET UNUSED OUTPUTS
        # ==========================================
        usedOutputs = set(segMap + gridMap)
        for pinName, var in mappingVars.items():
            outNum = int(pinName.replace("OUT", ""))
            if outNum not in usedOutputs:
                var.set("None")

        validate_mappings()

        # ==========================================
        # NEW: LOAD ADVANCED ANIMATION STEPS
        # ==========================================
        # Clear existing visual UI step rows before filling them
        for step in advancedSteps[:]:
            try:
                step.destroy()
            except:
                pass
        advancedSteps.clear()

        ser.reset_input_buffer()
        ser.write("LISTSTEPS\n".encode())
        start = time.time()
        
        while time.time() - start < 2:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                if line == "ENDSTEPS":
                    break
                elif line.startswith("COUNT="):
                    continue
                elif ":" in line:
                    # Format: "0:SCROLL,TEXT,2000,150"
                    prefix, data = line.split(":", 1)
                    tokens = data.split(",")
                    if len(tokens) == 4:
                        anim_type, anim_text, anim_duration, anim_speed = tokens
                        # Populate UI row using the loaded values
                        add_advanced_step(
                            anim=anim_type,
                            text=anim_text,
                            duration=anim_duration,
                            speed=anim_speed
                        )

        # ==========================================
        # APPLY BASE SETTINGS
        # ==========================================
        if "TEXT" in config:
            textEntry.delete(0, "end")
            textEntry.insert(0, config["TEXT"])

        if "SPEED" in config:
            speed = int(config["SPEED"])
            speedSlider.set(speed)
            update_speed(speed)

        if "SPACING" in config:
            spacing = int(config["SPACING"])
            spacingSlider.set(spacing)
            update_spacing(spacing)

        if "FORCESCROLL" in config:
            forceScrollVar.set(config["FORCESCROLL"] == "1")
            update_scroll_controls()

        if "ANIM" in config:
            mode = "advanced" if config["ANIM"] == "1" else "simple"
            displayModeVar.set(mode)
            on_display_mode_changed(mode)

        statusLabel.configure(text="> CONFIG LOADED")
        set_status_state("idle")

    except Exception as e:
        print("LOAD ERROR:", e)
        statusLabel.configure(text=f"Load failed")
        set_status_state("error")

def send_line(line):

    global ser

    if ser is None:
        return

    if not ser.is_open:
        return

    ser.write((line + "\n").encode())

    ser.flush()

    time.sleep(0.08)

def save_to_arduino():
    global ser, last_active_display_mode

    if ser is None:
        statusLabel.configure(text="Arduino not connected")
        set_status_state("error")
        return

    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        text = textEntry.get()
        speed = int(speedSlider.get())
        spacing = int(spacingSlider.get())
        force = 1 if forceScrollVar.get() else 0

        # Use the last viewed display mode (even if saving from the Hardware tab)
        mode = last_active_display_mode

        # ==========================================
        # SEND CONFIG
        # ==========================================
        send_line(f"TEXT={text}")
        send_line(f"SPEED={speed}")
        send_line(f"SPACING={spacing}")
        send_line(f"FORCESCROLL={force}")

        # ------------------------------------------
        # MODE 1: SIMPLE MODE SAVE (Wipe Advanced Data)
        # ------------------------------------------
        if mode == "simple":
            send_line("ANIM=0")
            send_line("CLEARSTEPS") # Clear advanced steps off the Arduino completely
            time.sleep(0.1)

        # ------------------------------------------
        # MODE 2: ADVANCED MODE SAVE (Save Both)
        # ------------------------------------------
        else:
            send_line("ANIM=1")
            send_line("CLEARSTEPS")
            time.sleep(0.2)

            if len(advancedSteps) == 0:
                statusLabel.configure(text="No advanced steps defined")
                return

            for step in advancedSteps:
                anim = step.animVar.get()
                text = step.textEntry.get()
                duration = step.durationEntry.get()
                speed = step.speedEntry.get()

                duration = duration.strip()
                speed = speed.strip()

                if duration == "": duration = "2000"
                if speed == "": speed = "150"

                anim = anim.strip().upper()
                text = text.strip()

                send_line(f"ADDSTEP={anim},{text},{duration},{speed}")

        # ==========================================
        # BUILD SEGMENT MAP
        # ==========================================
        segmentOrder = ["SEG_E", "SEG_D", "SEG_C", "SEG_DP", "SEG_A", "SEG_G", "SEG_F", "SEG_B"]
        segMap = []
        for segName in segmentOrder:
            found = -1
            for pinName, var in mappingVars.items():
                if var.get() == segName:
                    found = int(pinName.replace("OUT", ""))
                    break
            segMap.append(found)

        # ==========================================
        # BUILD GRID MAP
        # ==========================================
        gridMap = []
        for i in range(1, 8 + 1):
            gridName = f"GRID_{i}"
            found = -1
            for pinName, var in mappingVars.items():
                if var.get() == gridName:
                    found = int(pinName.replace("OUT", ""))
                    break
            gridMap.append(found)

        # ==========================================
        # SEND MAPS & SAVE
        # ==========================================
        segString = ",".join(str(x) for x in segMap)
        gridString = ",".join(str(x) for x in gridMap)

        send_line(f"SEGMAP={segString}")
        send_line(f"GRIDMAP={gridString}")
        send_line("SAVE")

        statusLabel.configure(text="> CONFIG SAVED")
        set_status_state("save")

    except Exception as e:
        print("SAVE ERROR:", e)
        statusLabel.configure(text=f"Send failed: {e}")
        set_status_state("error")

def refresh_ports():

    ports = get_ports()

    portMenu.configure(values=ports)

    portMenu.set(ports[0])

    statusLabel.configure(
        text="> PORTS REFRESHED"
    )

def reset_ui():

    global previewIndex
    global lastPreviewScroll

    # Reset preview animation state

    previewIndex = 0
    lastPreviewScroll = 0

    # Clear advanced animation steps

    for step in advancedSteps[:]:

        try:
            step.destroy()
        except:
            pass

    advancedSteps.clear()

    # Clear text

    textEntry.configure(state="normal")

    textEntry.delete(0, "end")

    # Reset sliders

    speedSlider.set(250)
    update_speed(250)

    spacingSlider.set(8)
    update_spacing(8)

    # Reset options

    forceScrollVar.set(False)

    # Clear preview

    previewCanvas.delete("all")

    # Reset mappings to defaults

    for pinName, var in mappingVars.items():

        var.set(
            defaultMappings.get(pinName, "None")
        )

    validate_mappings()

    # Disable controls

    set_controls_enabled(False)

    update_scroll_controls()

def monitor_connection():

    global ser

    if ser is not None:

        try:

            # Test serial connection

            ser.in_waiting

        except Exception:

            statusLabel.configure(
                text="> ARDUINO DISCONNECTED"
            )

            try:
                ser.close()
            except:
                pass

            ser = None

            reset_ui()

            set_status_state("disconnected")

    app.after(1000, monitor_connection)

# =====================================================
# RESET FUNCTIONS
# =====================================================

def reset_text():

    if ser is None:
        return

    textEntry.delete(0, "end")

    textEntry.insert(0, DEFAULT_TEXT)

    update_scroll_controls()


def reset_speed():

    if ser is None:
        return

    speedSlider.set(DEFAULT_SPEED)
    update_speed(DEFAULT_SPEED)


def reset_spacing():

    if ser is None:
        return

    spacingSlider.set(DEFAULT_SPACING)
    update_spacing(DEFAULT_SPACING)


def reset_force_scroll():

    if ser is None:
        return

    forceScrollVar.set(DEFAULT_FORCE_SCROLL)
    update_scroll_controls()


# =====================================================
# DISPLAY MODE
# =====================================================

def on_display_mode_changed(value):

    global last_active_display_mode
    last_active_display_mode = value

    simpleSettingsFrame.pack_forget()
    advancedSettingsFrame.pack_forget()

    if value == "simple":

        simpleSettingsFrame.pack(
            fill="x",
            padx=10,
            pady=10
        )

    else:

        advancedSettingsFrame.pack(
            fill="x",
            padx=10,
            pady=10
        )

# =====================================================
# UI HELPERS
# =====================================================

def update_speed(value):

    speedLabel.configure(
        text=f"SCROLL SPEED: {int(value)} ms"
    )

def update_spacing(value):

    spacingLabel.configure(
        text=f"SCROLL SPACING: {int(value)}"
    )

def safe_pack(widget, **kwargs):

    if not widget.winfo_manager():

        widget.pack(**kwargs)

def update_scroll_controls():

    text = textEntry.get()

    force = forceScrollVar.get()

    longText = len(text) > 8

    # =====================================
    # LONG TEXT
    # =====================================

    if longText:

        forceScrollRow.pack_forget()

        if not speedRow.winfo_manager():
            speedRow.pack()

        if not spacingRow.winfo_manager():
            spacingRow.pack()

    # =====================================
    # SHORT TEXT
    # =====================================

    else:

        if not forceScrollRow.winfo_manager():
            forceScrollRow.pack(pady=(0, 18))

        # ---------------------------------
        # FORCE SCROLL ENABLED
        # ---------------------------------

        if force:

            if not speedRow.winfo_manager():
                speedRow.pack()

            if not spacingRow.winfo_manager():
                spacingRow.pack()

        # ---------------------------------
        # FORCE SCROLL DISABLED
        # ---------------------------------

        else:

            speedRow.pack_forget()
            spacingRow.pack_forget()

# =====================================================
# RESET BUTTON FACTORY
# =====================================================

def create_reset_button(parent, command):
    return ctk.CTkButton(
        parent,
        text="↺",
        width=18,
        height=18,
        corner_radius=3,
        border_spacing=0,
        font=(FONT_MONO, 9, "bold"),
        fg_color=S_BORDER,
        hover_color=S_YELLOW_MID,
        text_color=S_YELLOW,
        command=command
    )

# =====================================================
# GLOBAL STATUS SYSTEM
# =====================================================

statusBlinkJob = None
currentStatusState = "disconnected"

def set_status_state(state):

    global statusBlinkJob
    global currentStatusState

    currentStatusState = state

    # ----------------------------------------
    # CANCEL CURRENT ANIMATION
    # ----------------------------------------

    if statusBlinkJob is not None:

        try:
            app.after_cancel(statusBlinkJob)
        except:
            pass

        statusBlinkJob = None
        currentStatusState = "disconnected"

    # ----------------------------------------
    # ALL OFF
    # ----------------------------------------

    redStatusLight.configure(fg_color=S_LIGHT_OFF)
    greenStatusLight.configure(fg_color=S_LIGHT_OFF)

    # ----------------------------------------
    # IDLE
    # Green blink every 5 sec
    # ----------------------------------------

    if state == "idle":

        idle_green_blink()

    # ----------------------------------------
    # PROBLEM
    # Solid red
    # ----------------------------------------

    elif state == "problem":

        redStatusLight.configure(
            fg_color=S_RED_ON
        )

    # ----------------------------------------
    # SAVE
    # ----------------------------------------

    elif state == "save":

        rapid_pulse("green", 20)

    # ----------------------------------------
    # ERROR
    # ----------------------------------------

    elif state == "error":

        rapid_pulse("red", 20)

    # ----------------------------------------
    # CONNECTING
    # heartbeat red/green
    # ----------------------------------------

    elif state == "connecting":

        connecting_heartbeat(0)

    # ----------------------------------------
    # CONNECTED SUCCESS
    # ----------------------------------------

    elif state == "connected_success":

        rapid_pulse("green", 20)

    # ----------------------------------------
    # FAILED CONNECTION
    # ----------------------------------------

    elif state == "failed_connection":

        rapid_pulse("red", 20)

    # ----------------------------------------
    # DISCONNECTING
    # ----------------------------------------

    elif state == "disconnecting":

        disconnect_pulse(0)

    # ----------------------------------------
    # DISCONNECTED
    # red blink every 5 sec
    # ----------------------------------------

    elif state == "disconnected":

        idle_red_blink()

    # ----------------------------------------
    # LOADING
    # ----------------------------------------

    elif state == "loading":

        loading_spinner(0)

def restore_idle_state():

    global ser

    # ----------------------------------------
    # CONNECTED = IDLE GREEN
    # ----------------------------------------

    if ser is not None and ser.is_open:

        set_status_state("idle")

    # ----------------------------------------
    # DISCONNECTED = IDLE RED
    # ----------------------------------------

    else:

        set_status_state("disconnected")

def rapid_pulse(color, step):

    global statusBlinkJob

    if step <= 0:

        restore_idle_state()

        return

    on = step % 2 == 0

    if color == "green":

        greenStatusLight.configure(
            fg_color=S_GREEN_ON if on else "#222222"
        )

        redStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    else:

        redStatusLight.configure(
            fg_color=S_RED_ON if on else "#222222"
        )

        greenStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    statusBlinkJob = app.after(
        50,
        lambda: rapid_pulse(color, step - 1)
    )

def idle_green_blink():

    global statusBlinkJob

    greenStatusLight.configure(
        fg_color=S_GREEN_ON
    )

    redStatusLight.configure(
        fg_color=S_LIGHT_OFF
    )

    statusBlinkJob = app.after(
        360,
        idle_green_off
    )

def idle_green_off():

    global statusBlinkJob

    greenStatusLight.configure(
        fg_color=S_LIGHT_OFF
    )

    statusBlinkJob = app.after(
        2500,
        idle_green_blink
    )

def idle_red_blink():

    global statusBlinkJob

    redStatusLight.configure(
        fg_color=S_RED_ON
    )

    greenStatusLight.configure(
        fg_color=S_LIGHT_OFF
    )

    statusBlinkJob = app.after(
        360,
        idle_red_off
    )

def idle_red_off():

    global statusBlinkJob

    redStatusLight.configure(
        fg_color=S_LIGHT_OFF
    )

    statusBlinkJob = app.after(
        2500,
        idle_red_blink
    )

def connecting_heartbeat(step):

    global statusBlinkJob

    # ----------------------------------------
    # ALTERNATING HEARTBEAT
    # ----------------------------------------

    pattern = [

        # RED ON
        (S_RED_ON, "#222222"),

        # BOTH OFF
        ("#222222", "#222222"),

        # GREEN ON
        ("#222222", S_GREEN_ON),

        # BOTH OFF
        ("#222222", "#222222"),
    ]

    redColor, greenColor = pattern[
        step % len(pattern)
    ]

    redStatusLight.configure(
        fg_color=redColor
    )

    greenStatusLight.configure(
        fg_color=greenColor
    )

    statusBlinkJob = app.after(
        140,
        lambda: connecting_heartbeat(step + 1)
    )

def disconnect_pulse(step):

    global statusBlinkJob

    if step >= 8:

        restore_idle_state()

        return

    on = step % 2 == 0

    colorRed = S_RED_ON if on else "#222222"
    colorGreen = S_GREEN_ON if on else "#222222"

    redStatusLight.configure(
        fg_color=colorRed
    )

    greenStatusLight.configure(
        fg_color=colorGreen
    )

    statusBlinkJob = app.after(
        90,
        lambda: disconnect_pulse(step + 1)
    )

def pulse_status_light(light, step):

    global statusBlinkJob

    if step >= 8:

        restore_idle_state()

        return

    on = step % 2 == 0

    if light == "green":

        greenStatusLight.configure(
            fg_color=S_GREEN_ON if on else "#222222"
        )

        redStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    else:

        redStatusLight.configure(
            fg_color=S_RED_ON if on else "#222222"
        )

        greenStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    statusBlinkJob = app.after(
        90,
        lambda: pulse_status_light(light, step + 1)
    )

def alternate_status_lights(step):

    global statusBlinkJob

    if step >= 10:

        greenStatusLight.configure(
            fg_color=S_GREEN_ON
        )

        redStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

        return

    if step % 2 == 0:

        greenStatusLight.configure(
            fg_color=S_GREEN_ON
        )

        redStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    else:

        redStatusLight.configure(
            fg_color=S_YELLOW
        )

        greenStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    statusBlinkJob = app.after(
        90,
        lambda: alternate_status_lights(step + 1)
    )

def disconnect_flash(step):

    global statusBlinkJob

    if step >= 6:

        redStatusLight.configure(
            fg_color=S_RED_ON
        )

        return

    color = S_RED_ON if step % 2 == 0 else "#222222"

    redStatusLight.configure(
        fg_color=color
    )

    greenStatusLight.configure(
        fg_color=S_LIGHT_OFF
    )

    statusBlinkJob = app.after(
        160,
        lambda: disconnect_flash(step + 1)
    )

def loading_spinner(step):

    global statusBlinkJob

    states = [
        (S_GREEN_ON, "#222222"),
        ("#222222", S_GREEN_ON),
    ]

    green, red = states[step % 2]

    greenStatusLight.configure(
        fg_color=green
    )

    redStatusLight.configure(
        fg_color=red
    )

    statusBlinkJob = app.after(
        200,
        lambda: loading_spinner(step + 1)
    )

def blink_status_light(light, step):

    global statusBlinkJob

    if step >= 6:

        restore_idle_state()

        return

    # ----------------------------------------
    # RED BLINK
    # ----------------------------------------

    if light == "red":

        color = S_RED_ON if step % 2 == 0 else "#222222"

        redStatusLight.configure(
            fg_color=color
        )

        greenStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    # ----------------------------------------
    # GREEN BLINK
    # ----------------------------------------

    else:

        color = S_GREEN_ON if step % 2 == 0 else "#222222"

        greenStatusLight.configure(
            fg_color=color
        )

        redStatusLight.configure(
            fg_color=S_LIGHT_OFF
        )

    statusBlinkJob = app.after(
        180,
        lambda: blink_status_light(light, step + 1)
    )

# =====================================================
# PREVIEW
# =====================================================

def draw_segment(x1, y1, x2, y2, on):

    color = S_VFD_ON if on else "#051a18"

    previewCanvas.create_rectangle(
        x1, y1, x2, y2,
        fill=color,
        outline=""
    )

def draw_digit(x, y, char):
    """
    Draws a VFD 7-segment digit with layered glow effect.
    """
    COLOR_ON   = "#00ffdd"   # Phosphor on
    COLOR_GLOW = "#004a42"   # Soft glow halo (1px wider, behind)
    COLOR_OFF  = "#041512"   # Dim unlit filament

    char = char.upper()
    base_char = char.replace(".", "")
    if base_char == "":
        base_char = " "
    active_set = SEGMENTS.get(base_char, "")

    w = 40   # digit width
    h = 80   # digit height
    t = 5    # segment thickness
    g = 2    # glow expansion

    def seg(x1, y1, x2, y2, on):
        if on:
            # Glow layer (slightly expanded, darker teal)
            previewCanvas.create_rectangle(
                x1 - g, y1 - g, x2 + g, y2 + g,
                fill=COLOR_GLOW, outline="")
            # Main bright segment
            previewCanvas.create_rectangle(
                x1, y1, x2, y2,
                fill=COLOR_ON, outline="")
        else:
            previewCanvas.create_rectangle(
                x1, y1, x2, y2,
                fill=COLOR_OFF, outline="")

    seg(x+t,     y,              x+w-t,   y+t,              "A" in active_set)  # Top
    seg(x+w-t,   y+t,            x+w,     y+(h//2)-2,       "B" in active_set)  # Top-right
    seg(x+w-t,   y+(h//2)+2,     x+w,     y+h-t,            "C" in active_set)  # Bot-right
    seg(x+t,     y+h-t,          x+w-t,   y+h,              "D" in active_set)  # Bottom
    seg(x,       y+(h//2)+2,     x+t,     y+h-t,            "E" in active_set)  # Bot-left
    seg(x,       y+t,            x+t,     y+(h//2)-2,       "F" in active_set)  # Top-left
    seg(x+t,     y+(h//2)-(t//2),x+w-t,   y+(h//2)+(t//2), "G" in active_set)  # Middle
    # Decimal point
    dp_on = "." in char
    if dp_on:
        previewCanvas.create_rectangle(
            x+w+4-g, y+h-t-g, x+w+4+t+g, y+h+g,
            fill=COLOR_GLOW, outline="")
        previewCanvas.create_rectangle(
            x+w+4, y+h-t, x+w+4+t, y+h,
            fill=COLOR_ON, outline="")
    else:
        previewCanvas.create_rectangle(
            x+w+4, y+h-t, x+w+4+t, y+h,
            fill=COLOR_OFF, outline="")

def update_preview():
    global previewIndex, lastPreviewScroll
    global py_current_step, py_step_start_time, py_last_frame_time, py_frame_index, py_blink_state

    previewCanvas.delete("all")
    mode = displayModeVar.get()

    # Get current timestamp in milliseconds
    now = int(time.time() * 1000)

    # ==========================================================
    # SIMPLE DISPLAY MODE BRANCH
    # ==========================================================
    if mode == "simple":
        text = textEntry.get().upper()
        if text == "":
            text = " "
        spacing = int(spacingSlider.get())
        force = forceScrollVar.get()
        speed = int(speedSlider.get())

        if len(text) <= 8 and not force:
            visible = text.ljust(8)
        else:
            padded = text + (" " * spacing)
            if now - lastPreviewScroll >= speed:
                lastPreviewScroll = now
                previewIndex += 1
                if previewIndex >= len(padded):
                    previewIndex = 0
            circular = padded + padded
            visible = circular[previewIndex:previewIndex + 8]

    # ==========================================================
    # ADVANCED DISPLAY MODE BRANCH
    # ==========================================================
    else:
        if len(advancedSteps) == 0:
            visible = "NO STEPS"
        else:
            # Boundary control safety check
            if py_current_step >= len(advancedSteps):
                py_current_step = 0

            step = advancedSteps[py_current_step]
            
            # Read variables safely directly from visual GUI rows
            anim_type = step.animVar.get().upper()
            anim_text = step.textEntry.get().upper()
            
            try:
                duration = int(step.durationEntry.get().strip())
            except:
                duration = 2000
                
            try:
                speed = int(step.speedEntry.get().strip())
            except:
                speed = 150

            # --------------------------------------------------
            # STATE UPDATE ENGINE (Mirrors Arduino behavior)
            # --------------------------------------------------
            if anim_type == "SCROLL":
                if now - py_last_frame_time >= speed:
                    py_last_frame_time = now
                    py_frame_index += 1

            elif anim_type == "TYPEWRITER":
                if now - py_last_frame_time >= speed:
                    py_last_frame_time = now
                    if py_frame_index < len(anim_text):
                        py_frame_index += 1

            elif anim_type == "BLINK":
                if now - py_last_frame_time >= speed:
                    py_last_frame_time = now
                    py_blink_state = not py_blink_state

            # Handle Step Sequence Timeline Progress
            if duration > 0:
                if now - py_step_start_time >= duration:
                    py_current_step += 1
                    if py_current_step >= len(advancedSteps):
                        py_current_step = 0
                    
                    # Reset state registers for the next step frame
                    py_step_start_time = now
                    py_last_frame_time = now
                    py_frame_index = 0
                    py_blink_state = False
                    
                    # Re-evaluate instantly on next tick loop iteration
                    app.after(30, update_preview)
                    return

            # --------------------------------------------------
            # FRAME STRING COMPILER (Mirrors Arduino logic)
            # --------------------------------------------------
            if anim_type == "STATIC":
                visible = anim_text.ljust(8)[:8]

            elif anim_type == "SCROLL":
                spacing = int(spacingSlider.get()) # Use global spacing slider for safety
                padded_msg = anim_text + (" " * spacing)
                if len(padded_msg) == 0:
                    padded_msg = " "
                
                window = ""
                for i in range(8):
                    idx = (py_frame_index + i) % len(padded_msg)
                    window += padded_msg[idx]
                visible = window

            elif anim_type == "BLINK":
                if py_blink_state:
                    visible = anim_text.ljust(8)[:8]
                else:
                    visible = "        "

            elif anim_type == "TYPEWRITER":
                amt = py_frame_index
                if amt > len(anim_text):
                    amt = len(anim_text)
                visible = anim_text[:amt].ljust(8)[:8]
            else:
                visible = "        "

    # ==========================================================
    # RENDERING THE CHARACTER PIPELINE (DOT-ONLY PROTOCOL)
    # ==========================================================

    # Canvas dimensions
    CANVAS_W = 580
    CANVAS_H = 160
    DIGIT_W  = 40
    DIGIT_H  = 80
    DIGIT_PITCH = 66        # horizontal distance between digit origins
    MARGIN_X = 18
    MARGIN_Y = 28           # top margin (space for bezel top)

    # ── Draw outer bezel border ─────────────────────────────────────────────
    BEZEL_PAD = 10
    previewCanvas.create_rectangle(
        BEZEL_PAD, BEZEL_PAD, CANVAS_W - BEZEL_PAD, CANVAS_H - BEZEL_PAD,
        outline="#1e3330", width=2, fill="")

    # ── Scanlines (subtle horizontal lines every 4px) ───────────────────────
    for sy in range(0, CANVAS_H, 4):
        previewCanvas.create_line(
            BEZEL_PAD+2, sy, CANVAS_W-BEZEL_PAD-2, sy,
            fill="#000000", width=1, stipple="gray25")

    # ── Tube slot separators (thin vertical lines between digits) ───────────
    for di in range(1, 8):
        sx = MARGIN_X + di * DIGIT_PITCH - 8
        previewCanvas.create_line(
            sx, BEZEL_PAD+6, sx, CANVAS_H-BEZEL_PAD-6,
            fill="#0d2a26", width=1)

    # ── Tube index labels ────────────────────────────────────────────────────
    for di in range(8):
        lx = MARGIN_X + di * DIGIT_PITCH + DIGIT_W // 2
        previewCanvas.create_text(
            lx, CANVAS_H - BEZEL_PAD - 8,
            text=f"T{di+1}", fill="#163d38",
            font=("Courier New", 7))

    # ── Corner notches ───────────────────────────────────────────────────────
    notch = 6
    for cx, cy, dx, dy in [
        (BEZEL_PAD, BEZEL_PAD, notch, notch),
        (CANVAS_W-BEZEL_PAD, BEZEL_PAD, -notch, notch),
        (BEZEL_PAD, CANVAS_H-BEZEL_PAD, notch, -notch),
        (CANVAS_W-BEZEL_PAD, CANVAS_H-BEZEL_PAD, -notch, -notch),
    ]:
        previewCanvas.create_line(cx, cy, cx+dx, cy, fill="#2a4f4a", width=1)
        previewCanvas.create_line(cx, cy, cx, cy+dy, fill="#2a4f4a", width=1)

    # ── Parse & paint tokens ─────────────────────────────────────────────────
    display_tokens = []
    char_index = 0
    while char_index < len(visible) and len(display_tokens) < 8:
        current_char = visible[char_index]
        if current_char == ".":
            display_tokens.append(current_char)
            char_index += 1
        elif char_index + 1 < len(visible) and visible[char_index + 1] == ".":
            display_tokens.append(current_char + visible[char_index + 1])
            char_index += 2
        else:
            display_tokens.append(current_char)
            char_index += 1
    while len(display_tokens) < 8:
        display_tokens.append(" ")

    x = MARGIN_X
    for token in display_tokens:
        draw_digit(x, MARGIN_Y, token)
        x += DIGIT_PITCH

    # Constant 30ms refresh rate
    app.after(30, update_preview)

# =====================================================
# WINDOW
# =====================================================

app = ctk.CTk()
app.title("Spengler Systems — Gizmo VFD Configurator")
app.configure(fg_color=S_BG)
app.after(100, lambda: app.state("zoomed"))

forceScrollVar = ctk.BooleanVar(value=False)

displayModeVar = ctk.StringVar(value="simple")

# =====================================================
# HARDWARE MAPPING DATA
# =====================================================

# =====================================================
# HARDWARE MAPPING DATA
# =====================================================

MAX_TOP_PINS = [
    "VCC", "DIN",
    "OUT0", "OUT1", "OUT2", "OUT3", "OUT4",
    "OUT5", "OUT6", "OUT7", "OUT8", "OUT9",
    "LOAD", "CLK"
]

MAX_BOTTOM_PINS = [
    "VBB", "DOUT",
    "OUT19", "OUT18", "OUT17", "OUT16", "OUT15",
    "OUT14", "OUT13", "OUT12", "OUT11", "OUT10",
    "BLANK", "GND"
]

mappingVars = {}
mappingMenus = {}
mappingLines = {}

saveStatus = "idle"

defaultMappings = {

    "OUT0":  "SEG_E",
    "OUT1":  "SEG_D",
    "OUT2":  "SEG_C",
    "OUT3":  "SEG_DP",
    "OUT4":  "SEG_B",
    "OUT5":  "SEG_A",
    "OUT6":  "SEG_G",
    "OUT7":  "SEG_F",

    "OUT8":  "None",
    "OUT9":  "None",

    "OUT10": "GRID_8",
    "OUT11": "GRID_7",
    "OUT12": "GRID_6",
    "OUT13": "GRID_5",
    "OUT14": "GRID_4",
    "OUT15": "GRID_3",
    "OUT16": "GRID_2",
    "OUT17": "GRID_1",

    "OUT18": "None",
    "OUT19": "None"
}

pin_positions = {}
lineObjects = {}

mappingOptions = [
    "None",
    "SEG_A", "SEG_B", "SEG_C", "SEG_D", "SEG_E", "SEG_F", "SEG_G", "SEG_DP",
    "GRID_1", "GRID_2", "GRID_3", "GRID_4",
    "GRID_5", "GRID_6", "GRID_7", "GRID_8"
]

# =====================================================
# HEADER BAR — SPENGLER SYSTEMS BRANDING
# =====================================================

# Red accent stripe — very top
accentStripe = ctk.CTkFrame(app, fg_color=S_RED, height=3, corner_radius=0)
accentStripe.pack(fill="x", side="top")
accentStripe.pack_propagate(False)

# Main header bar
headerBar = ctk.CTkFrame(app, fg_color=S_PANEL, corner_radius=0, border_width=0)
headerBar.pack(fill="x", side="top")

# Single content row — tight padding
headerInner = ctk.CTkFrame(headerBar, fg_color="transparent")
headerInner.pack(fill="x", padx=16, pady=(6, 6))

# Logo — small
try:
    _logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gb-logo.png")
    _pil_logo = Image.open(_logo_path).convert("RGBA")
    _ctk_logo = ctk.CTkImage(_pil_logo, size=(38, 38))
    ctk.CTkLabel(headerInner, image=_ctk_logo, text="").pack(side="left", padx=(0, 12))
except Exception as _e:
    print("Logo:", _e)

# Title + subtitle stacked
titleStack = ctk.CTkFrame(headerInner, fg_color="transparent")
titleStack.pack(side="left")

titleLabel = ctk.CTkLabel(titleStack, text="SPENGLER SYSTEMS",
    font=(FONT_MONO, 22, "bold"), text_color=S_RED, anchor="w")
titleLabel.pack(anchor="w")

subtitleLabel = ctk.CTkLabel(titleStack,
    text="GIZMO VFD DISPLAY CONFIGURATION TERMINAL",
    font=(FONT_MONO, 9), text_color=S_TEXT_DIM, anchor="w")
subtitleLabel.pack(anchor="w")

# ── STATUS LIGHTS — right side of header ─────────────────────────────────────
globalStatusFrame = ctk.CTkFrame(
    headerInner, fg_color=S_PANEL2,
    corner_radius=6, border_width=1, border_color=S_BORDER)
globalStatusFrame.pack(side="right")

ctk.CTkLabel(globalStatusFrame, text="SYS STATUS",
    font=(FONT_MONO, 7), text_color=S_TEXT_DIM).pack(pady=(4, 2), padx=10)

lightsRow = ctk.CTkFrame(globalStatusFrame, fg_color="transparent")
lightsRow.pack(pady=(0, 6), padx=10)

redStatusLight = ctk.CTkLabel(
    lightsRow, text="", width=14, height=14,
    corner_radius=7, fg_color=S_LIGHT_OFF)
redStatusLight.pack(side="left", padx=(0, 6))

greenStatusLight = ctk.CTkLabel(
    lightsRow, text="", width=14, height=14,
    corner_radius=7, fg_color=S_LIGHT_OFF)
greenStatusLight.pack(side="left")

# =====================================================
# TABVIEW
# =====================================================

tabview = ctk.CTkTabview(
    app,
    width=1350,
    height=720,
    fg_color=S_PANEL,
    segmented_button_fg_color=S_BG,
    segmented_button_selected_color=S_RED,
    segmented_button_selected_hover_color=S_RED_HOVER,
    segmented_button_unselected_color=S_BG,
    segmented_button_unselected_hover_color=S_PANEL2,
    text_color=S_TEXT,
    text_color_disabled=S_TEXT_DIM,
    border_width=1,
    border_color=S_BORDER
)

tabview.pack(padx=10, pady=10, fill="both", expand=True)

tabview.add("Display")
tabview.add("Hardware")

displayTab = tabview.tab("Display")
hardwareTab = tabview.tab("Hardware")

# =====================================================
# HARDWARE FRAME
# =====================================================

hardwareScroll = ctk.CTkFrame(
    hardwareTab,
    fg_color="transparent"
)

hardwareScroll.pack(
    fill="both",
    expand=True
)

# =====================================================
# TOP ROW
# =====================================================

topFrame = ctk.CTkFrame(
    displayTab,
    fg_color="transparent"
)

topFrame.pack(
    fill="x",
    padx=15,
    pady=10
)

# =====================================================
# CONNECTION FRAME
# =====================================================

connectionFrame = ctk.CTkFrame(
    topFrame,
    width=260,
    height=250,
    corner_radius=6,
    fg_color=S_PANEL2,
    border_width=1,
    border_color=S_BORDER
)

connectionFrame.pack(
    side="left",
    padx=10,
    fill="y"
)

connectionFrame.pack_configure(ipadx=10, ipady=10)

connectionFrame.pack_propagate(False)

ctk.CTkLabel(
    connectionFrame,
    text="CONNECTION",
    font=(FONT_MONO, 12, "bold"),
    text_color=S_YELLOW
).pack(pady=(14, 6))

separator1 = ctk.CTkFrame(connectionFrame, height=1, fg_color=S_BORDER)
separator1.pack(fill="x", padx=16, pady=(0, 12))

portMenu = ctk.CTkOptionMenu(
    connectionFrame,
    values=get_ports(),
    width=180,
    font=(FONT_MONO, 11),
    fg_color=S_PANEL,
    button_color=S_BORDER,
    button_hover_color=S_YELLOW_MID,
    text_color=S_TEXT,
    dropdown_fg_color=S_PANEL2,
    dropdown_text_color=S_TEXT,
    dropdown_hover_color=S_YELLOW_DIM
)

portMenu.pack(pady=8)

ctk.CTkButton(
    connectionFrame, text="REFRESH PORTS",
    command=refresh_ports, width=180, height=32,
    font=(FONT_MONO, 10), corner_radius=4,
    fg_color=S_PANEL, hover_color=S_BORDER,
    text_color=S_TEXT, border_width=1, border_color=S_BORDER
).pack(pady=6)

ctk.CTkButton(
    connectionFrame, text="CONNECT ARDUINO",
    command=connect_serial, width=180, height=34,
    font=(FONT_MONO, 10, "bold"), corner_radius=4,
    fg_color=S_RED, hover_color=S_RED_HOVER,
    text_color=S_TEXT_BRIGHT, border_width=0
).pack(pady=6)

statusLabel = ctk.CTkLabel(
    connectionFrame,
    text="> NOT CONNECTED",
    font=(FONT_MONO, 10),
    text_color=S_TEXT_DIM
)

statusLabel.pack(pady=15)

# =====================================================
# DISPLAY SETTINGS FRAME
# =====================================================

displayFrame = ctk.CTkFrame(
    topFrame,
    corner_radius=6,
    fg_color=S_PANEL2,
    border_width=1,
    border_color=S_BORDER
)

displayFrame.pack(
    side="left",
    padx=10,
    fill="both",
    expand=True
)

displayFrame.pack_configure(ipadx=10, ipady=10)

ctk.CTkLabel(
    displayFrame,
    text="DISPLAY SETTINGS",
    font=(FONT_MONO, 12, "bold"),
    text_color=S_YELLOW
).pack(pady=(14, 6))

# =====================================================
# DISPLAY MODE TOGGLE
# =====================================================

modeToggle = ctk.CTkSegmentedButton(
    displayFrame,
    values=["simple", "advanced"],
    variable=displayModeVar,
    command=on_display_mode_changed,
    width=260,
    height=32,
    font=(FONT_MONO, 11, "bold"),
    fg_color=S_PANEL,
    selected_color=S_YELLOW_MID,
    selected_hover_color=S_YELLOW_MID,
    unselected_color=S_PANEL,
    unselected_hover_color=S_PANEL2,
    text_color=S_YELLOW,
    text_color_disabled=S_TEXT_DIM
)

modeToggle.pack(pady=(0, 12))

modeToggle.set("simple")

separator2 = ctk.CTkFrame(displayFrame, height=1, fg_color=S_BORDER)
separator2.pack(fill="x", padx=16, pady=(0, 12))

# =====================================================
# SETTINGS MODE CONTAINERS
# =====================================================

simpleSettingsFrame = ctk.CTkFrame(
    displayFrame,
    fg_color="transparent"
)

advancedSettingsFrame = ctk.CTkFrame(
    displayFrame,
    fg_color="transparent"
)

simpleSettingsFrame.pack(
    fill="x",
    padx=10,
    pady=10
)

# =====================================================
# TEXT ROW
# =====================================================

textLabel = ctk.CTkLabel(
    displayFrame,
    text="DISPLAY TEXT",
    font=(FONT_MONO, 10, "bold"),
    text_color=S_TEXT_DIM
)

textLabel.pack(in_=simpleSettingsFrame)

textRow = ctk.CTkFrame(
    simpleSettingsFrame,
    fg_color="transparent"
)

textRow.pack(pady=(6, 18))

textEntry = ctk.CTkEntry(
    textRow, width=500, height=36,
    font=(FONT_MONO, 14),
    fg_color=S_VFD_BG, border_color=S_BORDER,
    text_color=S_VFD_ON, placeholder_text="> ENTER TEXT",
    placeholder_text_color=S_TEXT_DIM
)

textEntry.pack(side="left")

textResetButton = create_reset_button(
    textRow,
    reset_text
)

textResetButton.pack(side="left", padx=(8, 0))

textEntry.bind(
    "<KeyRelease>",
    lambda e: update_scroll_controls()
)

# =====================================================
# SPEED ROW
# =====================================================

speedRow = ctk.CTkFrame(
    simpleSettingsFrame,
    fg_color="transparent"
)

speedLabel = ctk.CTkLabel(
    speedRow,
    text="Scroll Speed: 250 ms",
    font=("Arial", 14)
)

speedLabel.pack()

speedControlRow = ctk.CTkFrame(
    speedRow,
    fg_color="transparent"
)

speedControlRow.pack(pady=(6, 18))

speedSlider = ctk.CTkSlider(
    speedControlRow, from_=50, to=1000, width=350,
    command=update_speed,
    button_color=S_YELLOW, button_hover_color=S_YELLOW,
    progress_color=S_YELLOW_MID, fg_color=S_BORDER2
)

speedSlider.set(DEFAULT_SPEED)

speedSlider.pack(side="left")

speedResetButton = create_reset_button(
    speedControlRow,
    reset_speed
)

speedResetButton.pack(side="left", padx=(8, 0))

speedRow.pack()

# =====================================================
# SPACING ROW
# =====================================================

spacingRow = ctk.CTkFrame(
    simpleSettingsFrame,
    fg_color="transparent"
)

spacingLabel = ctk.CTkLabel(
    spacingRow,
    text="Scroll Spacing: 8",
    font=("Arial", 14)
)

spacingLabel.pack()

spacingControlRow = ctk.CTkFrame(
    spacingRow,
    fg_color="transparent"
)

spacingControlRow.pack(pady=(6, 18))

spacingSlider = ctk.CTkSlider(
    spacingControlRow, from_=1, to=20, number_of_steps=19, width=350,
    command=update_spacing,
    button_color=S_YELLOW, button_hover_color=S_YELLOW,
    progress_color=S_YELLOW_MID, fg_color=S_BORDER2
)

spacingSlider.set(DEFAULT_SPACING)

spacingSlider.pack(side="left")

spacingResetButton = create_reset_button(
    spacingControlRow,
    reset_spacing
)

spacingResetButton.pack(side="left", padx=(8, 0))

spacingRow.pack()

# =====================================================
# FORCE SCROLL ROW
# =====================================================

forceScrollRow = ctk.CTkFrame(
    simpleSettingsFrame,
    fg_color="transparent"
)

forceScrollCheck = ctk.CTkCheckBox(
    forceScrollRow,
    text="FORCE SCROLL",
    variable=forceScrollVar,
    font=(FONT_MONO, 11),
    text_color=S_TEXT,
    fg_color=S_YELLOW_MID,
    hover_color=S_YELLOW_MID,
    checkmark_color=S_BG,
    border_color=S_BORDER
)

forceScrollCheck.pack(side="left")

forceResetButton = create_reset_button(
    forceScrollRow,
    reset_force_scroll
)

forceResetButton.pack(side="left", padx=(8, 0))

forceScrollVar.trace_add(
    "write",
    lambda *args: update_scroll_controls()
)

forceScrollRow.pack(pady=(0, 18))

# =====================================================
# ADVANCED ANIMATION EDITOR
# =====================================================

advancedTitle = ctk.CTkLabel(
    advancedSettingsFrame,
    text="ANIMATION SEQUENCE",
    font=(FONT_MONO, 11, "bold"),
    text_color=S_YELLOW
)

advancedTitle.pack(pady=(6, 8))

# =====================================================
# ADVANCED TABLE WRAPPER
# =====================================================

advancedTableFrame = ctk.CTkFrame(
    advancedSettingsFrame,
    fg_color="transparent"
)

advancedTableFrame.pack(
    fill="x",
    padx=10,
    pady=(0, 10)
)

# =====================================================
# HEADER ROW
# =====================================================

headerRow = ctk.CTkFrame(
    advancedTableFrame,
    fg_color="transparent"
)

headerRow.pack(
    fill="x",
    padx=(10, 0),
    pady=(0, 4)
)

ctk.CTkLabel(
    headerRow,
    text="ANIMATION",
    font=(FONT_MONO, 10, "bold"),
    text_color=S_TEXT_DIM,
    width=100,
    anchor="w"
).grid(row=0, column=0, padx=(8, 12), sticky="w")

ctk.CTkLabel(
    headerRow,
    text="TEXT",
    font=(FONT_MONO, 10, "bold"),
    text_color=S_TEXT_DIM,
    width=160,
    anchor="w"
).grid(row=0, column=1, padx=(0, 12), sticky="w")

ctk.CTkLabel(
    headerRow,
    text="DURATION",
    font=(FONT_MONO, 10, "bold"),
    text_color=S_TEXT_DIM,
    width=70,
    anchor="w"
).grid(row=0, column=2, padx=(0, 12), sticky="w")

ctk.CTkLabel(
    headerRow,
    text="SPEED",
    font=(FONT_MONO, 10, "bold"),
    text_color=S_TEXT_DIM,
    width=70,
    anchor="w"
).grid(row=0, column=3, padx=(0, 12), sticky="w")

# =====================================================
# SCROLLABLE STEP LIST
# =====================================================

stepListFrame = ctk.CTkScrollableFrame(
    advancedTableFrame, width=560, height=100,
    fg_color=S_PANEL2, border_width=1, border_color=S_BORDER
)

stepListFrame.pack(
    fill="x"
)

# =====================================================
# STEP STORAGE
# =====================================================

advancedSteps = []

# =====================================================
# REMOVE STEP
# =====================================================

def remove_advanced_step(stepFrame):

    if stepFrame in advancedSteps:

        advancedSteps.remove(stepFrame)

    stepFrame.destroy()

# =====================================================
# ADD STEP
# =====================================================

def add_advanced_step(
    anim="SCROLL",
    text="HELLO",
    duration="2000",
    speed="150"
):

    row = ctk.CTkFrame(
        stepListFrame, fg_color=S_PANEL,
        corner_radius=4, border_width=1, border_color=S_BORDER2
    )

    row.pack(
        fill="x",
        pady=2,
        padx=0
    )

    # ------------------------------------------
    # ANIMATION TYPE
    # ------------------------------------------

    animVar = ctk.StringVar(value=anim)

    animMenu = ctk.CTkOptionMenu(
        row, values=["STATIC","SCROLL","BLINK","TYPEWRITER"],
        variable=animVar, width=100, height=30, dynamic_resizing=False,
        font=(FONT_MONO, 10), fg_color=S_PANEL2,
        button_color=S_BORDER, button_hover_color=S_YELLOW_MID,
        text_color=S_TEXT, dropdown_fg_color=S_PANEL2,
        dropdown_text_color=S_TEXT, dropdown_hover_color=S_YELLOW_DIM
    )


    animMenu.grid(
        row=0,
        column=0,
        padx=(8, 12),
        pady=4,
        sticky="w"
    )

    # ------------------------------------------
    # TEXT
    # ------------------------------------------

    textEntry = ctk.CTkEntry(
        row, width=160, height=30,
        font=(FONT_MONO, 10), fg_color=S_VFD_BG,
        border_color=S_BORDER, text_color=S_VFD_ON
    )

    textEntry.insert(0, text)

    textEntry.grid(
        row=0,
        column=1,
        padx=(0, 12),
        sticky="w"
    )

    # ------------------------------------------
    # DURATION
    # ------------------------------------------

    durationEntry = ctk.CTkEntry(
        row, width=70, height=30,
        font=(FONT_MONO, 10), fg_color=S_PANEL2,
        border_color=S_BORDER, text_color=S_TEXT
    )

    durationEntry.insert(0, duration)

    durationEntry.grid(
        row=0,
        column=2,
        padx=(0, 12),
        sticky="w"
    )

    # ------------------------------------------
    # SPEED
    # ------------------------------------------

    speedEntry = ctk.CTkEntry(
        row, width=70, height=30,
        font=(FONT_MONO, 10), fg_color=S_PANEL2,
        border_color=S_BORDER, text_color=S_TEXT
    )

    speedEntry.insert(0, speed)

    speedEntry.grid(
        row=0,
        column=3,
        padx=(0, 12),
        sticky="w"
    )

    # ------------------------------------------
    # REMOVE BUTTON
    # ------------------------------------------

    removeButton = ctk.CTkButton(
        row, text="✕", width=28, height=28,
        font=(FONT_MONO, 10), fg_color=S_RED_DIM,
        hover_color=S_RED, text_color=S_TEXT_BRIGHT, corner_radius=4,
        command=lambda: remove_advanced_step(row)
    )

    removeButton.grid(
        row=0,
        column=4,
        padx=(0, 8)
    )

    row.animVar = animVar
    row.textEntry = textEntry
    row.durationEntry = durationEntry
    row.speedEntry = speedEntry

    advancedSteps.append(row)

    global py_current_step, py_step_start_time, py_frame_index
    py_current_step = 0
    py_step_start_time = int(time.time() * 1000)
    py_frame_index = 0

# =====================================================
# ADD BUTTON
# =====================================================

addStepButton = ctk.CTkButton(
    advancedSettingsFrame, text="+ ADD STEP",
    height=32, command=add_advanced_step,
    font=(FONT_MONO, 10, "bold"), corner_radius=4,
    fg_color=S_PANEL, hover_color=S_BORDER,
    text_color=S_YELLOW, border_width=1, border_color=S_YELLOW_MID
)

addStepButton.pack(
    padx=10,
    pady=(0, 10),
    fill="x"
)



# =====================================================
# PREVIEW FRAME
# =====================================================

previewFrame = ctk.CTkFrame(
    displayTab, corner_radius=6,
    fg_color=S_PANEL2, border_width=1, border_color=S_BORDER
)

previewFrame.pack(
    fill="x",
    padx=25,
    pady=(5, 10)
)

ctk.CTkLabel(
    previewFrame, text="VFD PREVIEW",
    font=(FONT_MONO, 10, "bold"), text_color=S_TEXT_DIM
).pack(pady=(10, 6))

separator4 = ctk.CTkFrame(previewFrame, height=1, fg_color=S_BORDER)
separator4.pack(fill="x", padx=16, pady=(0, 10))

previewCanvas = tk.Canvas(
    previewFrame, width=580, height=160,
    bg=S_VFD_BG, highlightthickness=0
)

previewCanvas.pack(pady=5)

# =====================================================
# SAVE BUTTON
# =====================================================

saveButtonDisplay = ctk.CTkButton(
    displayTab, text="▶  SAVE TO ARDUINO",
    command=save_to_arduino, width=280, height=42,
    font=(FONT_MONO, 13, "bold"), corner_radius=4,
    fg_color=S_RED, hover_color=S_RED_HOVER,
    text_color=S_TEXT_BRIGHT
)

saveButtonDisplay.pack(pady=(0, 20))

# =====================================================
# HARDWARE TAB
# =====================================================

hardwareTitle = ctk.CTkLabel(
    hardwareScroll, text="MAX6921 — HARDWARE MAPPING",
    font=(FONT_MONO, 16, "bold"), text_color=S_RED
)

hardwareTitle.pack(pady=(20, 5))

hardwareInfo = ctk.CTkLabel(
    hardwareScroll,
    text="ASSIGN MAX6921 OUTPUTS TO SEGMENTS AND GRIDS",
    font=(FONT_MONO, 9), text_color=S_TEXT_DIM
)

hardwareInfo.pack(pady=(0, 15))

mappingStatusLabel = ctk.CTkLabel(
    hardwareScroll, text="",
    font=(FONT_MONO, 10), text_color=S_TEXT_DIM
)

mappingStatusLabel.pack(pady=(0, 10))

saveButtonHardware = ctk.CTkButton(
    hardwareScroll, text="▶  SAVE TO ARDUINO",
    command=save_to_arduino, width=280, height=42,
    font=(FONT_MONO, 13, "bold"), corner_radius=4,
    fg_color=S_RED, hover_color=S_RED_HOVER,
    text_color=S_TEXT_BRIGHT
)

saveButtonHardware.pack(pady=(0, 15))

# =====================================================
# CHIP CANVAS
# =====================================================

chipCanvas = tk.Canvas(
    hardwareScroll, width=1650, height=520,
    bg=S_BG, highlightthickness=1, highlightbackground=S_BORDER
)

chipCanvas.pack(pady=20)

# =====================================================
# 7 SEGMENT REFERENCE BUTTON
# =====================================================

def open_segment_reference():

    refWindow = ctk.CTkToplevel(app)
    refWindow.title("7-SEG REFERENCE")
    refWindow.geometry("300x420")
    refWindow.resizable(False, False)
    refWindow.configure(fg_color=S_BG)
    refWindow.grab_set()
    ctk.CTkLabel(refWindow, text="7-SEGMENT REFERENCE",
        font=(FONT_MONO, 12, "bold"), text_color=S_YELLOW
    ).pack(pady=(15, 10))
    guideCanvas = tk.Canvas(
        refWindow, width=220, height=320,
        bg=S_VFD_BG, highlightthickness=1, highlightbackground=S_BORDER
    )

    guideCanvas.pack(padx=20, pady=10)

    # -----------------------------------------
    # SEGMENTS
    # -----------------------------------------

    guideCanvas.create_rectangle(
        70, 20, 150, 35,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        110, 10,
        text="A",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        155, 40, 170, 120,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        185, 80,
        text="B",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        155, 160, 170, 240,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        185, 200,
        text="C",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        70, 245, 150, 260,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        110, 275,
        text="D",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        50, 160, 65, 240,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        30, 200,
        text="E",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        50, 40, 65, 120,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        30, 80,
        text="F",
        fill=S_TEXT_DIM
    )

    guideCanvas.create_rectangle(
        70, 135, 150, 150,
        fill=S_YELLOW
    )

    guideCanvas.create_text(
        110, 120,
        text="G",
        fill=S_TEXT_DIM
    )

# =====================================================
# INFO BUTTON
# =====================================================

segmentInfoButton = ctk.CTkButton(
    hardwareScroll, text="7-SEG REFERENCE",
    command=open_segment_reference, width=200, height=30,
    font=(FONT_MONO, 9), corner_radius=4,
    fg_color=S_PANEL2, hover_color=S_PANEL,
    text_color=S_TEXT_DIM, border_width=1, border_color=S_BORDER
)

segmentInfoButton.pack(pady=(0, 20))

# =====================================================
# CHIP BODY
# =====================================================

CHIP_LEFT = 180
CHIP_RIGHT = 1470
CHIP_TOP = 140
CHIP_BOTTOM = 380

chipCanvas.create_rectangle(
    CHIP_LEFT, CHIP_TOP, CHIP_RIGHT, CHIP_BOTTOM,
    fill=S_PANEL2, outline=S_BORDER, width=2
)

chipCanvas.create_text(
    (CHIP_LEFT + CHIP_RIGHT) / 2,
    (CHIP_TOP + CHIP_BOTTOM) / 2,
    text="MAX6921",
    fill=S_BORDER,
    font=(FONT_MONO, 34, "bold")
)

# =====================================================
# PIN DEFINITIONS
# =====================================================

topPins = [
    "VCC", "DIN",
    "OUT0", "OUT1", "OUT2", "OUT3", "OUT4",
    "OUT5", "OUT6", "OUT7", "OUT8", "OUT9",
    "LOAD", "CLK"
]

bottomPins = [
    "VBB", "DOUT",
    "OUT19", "OUT18", "OUT17", "OUT16", "OUT15",
    "OUT14", "OUT13", "OUT12", "OUT11", "OUT10",
    "BLANK", "GND"
]

# =====================================================
# VALIDATION
# =====================================================

def validate_mappings():

    assigned = {}
    duplicates = {}

    # ==========================================
    # RESET COLORS
    # ==========================================

    for pin, menu in mappingMenus.items():

        menu.configure(
            fg_color=S_PANEL2
        )

        if pin in lineObjects:

            chipCanvas.itemconfig(
                lineObjects[pin],
                fill=S_YELLOW
            )

    # ==========================================
    # BUILD ASSIGNMENT TABLE
    # ==========================================

    for pin, var in mappingVars.items():

        value = var.get()

        if value == "None":
            continue

        if value not in assigned:
            assigned[value] = []

        assigned[value].append(pin)

    # ==========================================
    # FIND DUPLICATES
    # ==========================================

    duplicateMessages = []

    for value, pins in assigned.items():

        if len(pins) > 1:

            duplicates[value] = pins

            duplicateMessages.append(
                f"{value} on {', '.join(pins)}"
            )

            # ------------------------------
            # RED HIGHLIGHT
            # ------------------------------

            for pin in pins:

                mappingMenus[pin].configure(
                    fg_color=S_RED_MID
                )

                chipCanvas.itemconfig(
                    lineObjects[pin],
                    fill=S_RED_ON
                )

    # ==========================================
    # REQUIRED SEGMENTS
    # ==========================================

    requiredSegs = [
        "SEG_A",
        "SEG_B",
        "SEG_C",
        "SEG_D",
        "SEG_E",
        "SEG_F",
        "SEG_G"
    ]

    requiredGrids = [
        "GRID_1",
        "GRID_2",
        "GRID_3",
        "GRID_4",
        "GRID_5",
        "GRID_6",
        "GRID_7",
        "GRID_8"
    ]

    missing = []

    for seg in requiredSegs:

        if seg not in assigned:
            missing.append(seg)

    for grid in requiredGrids:

        if grid not in assigned:
            missing.append(grid)

    # ==========================================
    # ERROR TEXT
    # ==========================================

    problems = []

    if duplicateMessages:

        problems.append(
            "Duplicates:\n" +
            "\n".join(duplicateMessages)
        )

    if missing:

        problems.append(
            "Missing:\n" +
            ", ".join(missing)
        )

    # ==========================================
    # INVALID
    # ==========================================

    if problems:

        mappingStatusLabel.configure(
            text="\n\n".join(problems),
            text_color=S_RED
        )

        set_status_state("problem")

        if ser is not None:

            saveButtonDisplay.configure(
                state="disabled"
            )

            saveButtonHardware.configure(
                state="disabled"
            )

        return False

    # ==========================================
    # VALID
    # ==========================================

    mappingStatusLabel.configure(
        text="Mapping valid",
        text_color=S_GREEN_ON
    )

    set_status_state("idle")

    if ser is not None:

        saveButtonDisplay.configure(
            state="normal"
        )

        saveButtonHardware.configure(
            state="normal"
        )

    return True

# =====================================================
# CALLBACK
# =====================================================

def on_mapping_changed(choice):

    validate_mappings()

# =====================================================
# DRAW PINS
# =====================================================

TOP_Y_PIN = 170
BOTTOM_Y_PIN = 350

TOP_Y_LABEL = 112
BOTTOM_Y_LABEL = 408

TOP_Y_MENU = 62
BOTTOM_Y_MENU = 468

PIN_COUNT = 14

# Evenly distribute pins across chip width

pinSpacing = (CHIP_RIGHT - CHIP_LEFT) / (PIN_COUNT - 1)

# =====================================================
# TOP PINS
# =====================================================

for i, pin in enumerate(topPins):

    x = CHIP_LEFT + (i * pinSpacing)

    # Pin leg

    # Pin metal body

    chipCanvas.create_rectangle(
        x - 8,
        TOP_Y_PIN - 10,
        x + 8,
        TOP_Y_PIN + 6,
        fill=S_BORDER,
        outline=""
    )

    # Pin leg

    chipCanvas.create_line(
        x,
        TOP_Y_PIN - 8,
        x,
        TOP_Y_PIN - 50,
        fill=S_BORDER2,
        width=6
    )

    # Pin label

    chipCanvas.create_text(
        x,
        TOP_Y_LABEL,
        text=pin,
        fill=S_TEXT_DIM,
        font=("Arial", 10, "bold")
    )

    # Configurable outputs

    if pin.startswith("OUT"):

        var = StringVar(
            value=defaultMappings.get(pin, "None")
        )

        mappingVars[pin] = var

        menu = ctk.CTkOptionMenu(
            hardwareScroll, values=mappingOptions,
            variable=var, width=72, height=22,
            command=on_mapping_changed,
            font=(FONT_MONO, 9), fg_color=S_PANEL2,
            button_color=S_BORDER, button_hover_color=S_YELLOW_MID,
            text_color=S_TEXT, dropdown_fg_color=S_PANEL2,
            dropdown_text_color=S_TEXT, dropdown_hover_color=S_YELLOW_DIM
        )

        mappingMenus[pin] = menu

        chipCanvas.create_window(
            x,
            TOP_Y_MENU,
            window=menu
        )

        # Trace to dropdown

        line = chipCanvas.create_line(
            x,
            TOP_Y_PIN - 40,
            x,
            TOP_Y_MENU + 14,
            fill=S_YELLOW,
            width=2
        )

        lineObjects[pin] = line

# =====================================================
# BOTTOM PINS
# =====================================================

for i, pin in enumerate(bottomPins):

    x = CHIP_LEFT + (i * pinSpacing)

    # Pin leg

    # Pin metal body

    chipCanvas.create_rectangle(
        x - 8,
        BOTTOM_Y_PIN - 6,
        x + 8,
        BOTTOM_Y_PIN + 10,
        fill=S_BORDER,
        outline=""
    )

    # Pin leg

    chipCanvas.create_line(
        x,
        BOTTOM_Y_PIN + 8,
        x,
        BOTTOM_Y_PIN + 50,
        fill=S_BORDER2,
        width=6
    )

    # Pin label

    chipCanvas.create_text(
        x,
        BOTTOM_Y_LABEL,
        text=pin,
        fill=S_TEXT_DIM,
        font=("Arial", 10, "bold")
    )

    # Configurable outputs

    if pin.startswith("OUT"):

        var = StringVar(
            value=defaultMappings.get(pin, "None")
        )

        mappingVars[pin] = var

        menu = ctk.CTkOptionMenu(
            hardwareScroll, values=mappingOptions,
            variable=var, width=72, height=22,
            command=on_mapping_changed,
            font=(FONT_MONO, 9), fg_color=S_PANEL2,
            button_color=S_BORDER, button_hover_color=S_YELLOW_MID,
            text_color=S_TEXT, dropdown_fg_color=S_PANEL2,
            dropdown_text_color=S_TEXT, dropdown_hover_color=S_YELLOW_DIM
        )

        mappingMenus[pin] = menu

        chipCanvas.create_window(
            x,
            BOTTOM_Y_MENU,
            window=menu
        )

        # Trace to dropdown

        line = chipCanvas.create_line(
            x,
            BOTTOM_Y_PIN + 40,
            x,
            BOTTOM_Y_MENU - 14,
            fill=S_YELLOW,
            width=2
        )

        lineObjects[pin] = line

# =====================================================
# INITIAL VALIDATION
# =====================================================

validate_mappings()

# =====================================================
# RESET BUTTON VISIBILITY
# =====================================================

def set_reset_buttons_visible(visible):

    # -----------------------------------------
    # SHOW
    # -----------------------------------------

    if visible:

        if not textResetButton.winfo_manager():
            textResetButton.pack(side="left", padx=(8, 0))

        if not speedResetButton.winfo_manager():
            speedResetButton.pack(side="left", padx=(8, 0))

        if not spacingResetButton.winfo_manager():
            spacingResetButton.pack(side="left", padx=(8, 0))

        if not forceResetButton.winfo_manager():
            forceResetButton.pack(side="left", padx=(8, 0))

    # -----------------------------------------
    # HIDE
    # -----------------------------------------

    else:

        textResetButton.pack_forget()

        speedResetButton.pack_forget()

        spacingResetButton.pack_forget()

        forceResetButton.pack_forget()

# =====================================================
# CONTROL ENABLING
# =====================================================

def set_controls_enabled(enabled):

    state = "normal" if enabled else "disabled"

    # ==========================================
    # DISPLAY CONTROLS
    # ==========================================

    textEntry.configure(state=state)

    speedSlider.configure(state=state)

    spacingSlider.configure(state=state)

    forceScrollCheck.configure(state=state)

    modeToggle.configure(state=state)

    addStepButton.configure(state=state)

    for step in advancedSteps:

        for child in step.winfo_children():

            try:
                child.configure(state=state)
            except:
                pass

    # ==========================================
    # HARDWARE CONTROLS
    # ==========================================

    for menu in mappingMenus.values():

        menu.configure(state=state)

    # ==========================================
    # SAVE BUTTON
    # ==========================================

    if enabled:

        validate_mappings()

    else:

        saveButtonDisplay.configure(state="disabled")
        saveButtonHardware.configure(state="disabled")

    # ==========================================
    # PREVIEW
    # ==========================================

    if enabled:

        previewCanvas.configure(bg=S_VFD_BG)

    else:

        previewCanvas.configure(bg="#030b0a")

    # ==========================================
    # RESET BUTTON VISIBILITY
    # ==========================================

    set_reset_buttons_visible(enabled)

# =====================================================
# START
# =====================================================

set_controls_enabled(False)

update_scroll_controls()

set_status_state("disconnected")

monitor_connection()

update_preview()

app.mainloop()