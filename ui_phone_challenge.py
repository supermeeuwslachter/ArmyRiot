import os
import queue
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import WebDriverException


# ====== Configuration ======
PHONE_ID = os.getenv("PHONE_ID", "192.168.0.102:36665")
APPIUM_SERVER = os.getenv("APPIUM_SERVER", "http://127.0.0.1:4723")
PHONE_PIN = os.getenv("PHONE_PIN", "11554422")
TARGET_URL = "https://supermeeuwslachter.github.io/ArmyRiot/"
DESKTOP_BACKGROUND_IMAGE = os.path.join(os.path.dirname(__file__), "bean.jpg")
WINDOWS_ICON_IMAGE = os.path.join(os.path.dirname(__file__), "windows_icon.png")
PHONE_FLOW_SCRIPT = os.path.join(os.path.dirname(__file__), "phone_notes_then_open_link.py")
BRIEF_MYCROFT_IMAGE = os.path.join(os.path.dirname(__file__), "brief_mycroft.png")
TASKBAR_HEIGHT = 40
EYE_HOTSPOT_X_RATIO = float(os.getenv("EYE_HOTSPOT_X_RATIO", "0.36"))
EYE_HOTSPOT_Y_RATIO = float(os.getenv("EYE_HOTSPOT_Y_RATIO", "0.40"))
EYE_HOTSPOT_RADIUS_PX = int(os.getenv("EYE_HOTSPOT_RADIUS_PX", "24"))

# Single riddle gate on the home screen.
HOME_RIDDLE = (
    "The doors of the Diogenes Club creak open with hushed reverence. Gas lamps flicker in the silence, and a familiar voice, heavy with authority, declares: Enter quietly, observer... and let your mind prepare for the impossible conversation. You step into the shadowed alcove and feel the weight of secrets hanging in the air, filled with cigar smoke, chemical traces and whispered treachery. Before you unfolds a clandestine meeting, winding through words where crystal and glass reflect like diamonds. Wood paneling conceals secrets like clubs. Iron fixtures cast shadows like spades of conspiracy and where the silk curtains reveal truths like hearts of hatred and ambition, but also of respect and calculation. You know that every word carries double meaning. The path lies hidden in phrases, four per exchange, concealed in the verbal dance of these masterful minds. Wherein the students always wear suits, ties and hats, a governess is obsessed with mechanics, a professor focusses on formulae and a detective investigates the anatomy of the body. Sometimes numbers hold power, where a code is a code. Sometimes as dark as poisoned wine. Find them, and you shall know which cards lead you through this deadly game. Where the majority always wins."
)
HOME_RIDDLE_ANSWER = os.getenv("HOME_RIDDLE_ANSWER", "31CBE2")

LETTER_TEXT = (
    "My Dearest Brother,\n"
    "\n"
    "Should this letter find its way into your hands, I fear I have by now departed this "
    "mortal world - the physicians, I expect, shall attribute my passing to a failure of the heart. "
    "I implore you, however, to resist such a convenient conclusion.\n"
    "\n"
    "My death was no natural affliction. I have been poisoned - administered a most cunning and "
    "diabolical substance, one artfully designed to present itself to the uninitiated eye as cardiac "
    "arrest. The villain responsible has been meticulous, but not meticulous enough.\n"
    "\n"
    "I had not yet completed my enquiries into the deaths of my colleagues - a matter most grave, "
    "which I had been pursuing with considerable diligence. Nevertheless, I have accumulated a "
    "body of evidence of no small consequence, sufficient, I believe, to unmask the perpetrator, "
    "should one possess the acuity to interpret it correctly.\n"
    "\n"
    "To this end, I have devised a series of challenges - a quest, if you will - through which this "
    "intelligence shall be transmitted to you, and to you alone. Only a mind of exceptional "
    "sharpness and resourcefulness shall prove capable of completing it; a mind, I trust, very much "
    "like your own.\n"
    "\n"
    "You shall commence by directing your pocket telephone to the address inscribed below. "
    "Upon the successful resolution of the quest, all that I have discovered shall be laid bare before you.\n"
    "\n"
    "Yours in perpetual fraternal devotion,"
)

VOICE_RECORDER_PACKAGES = [
    "com.sec.android.app.voicenote",
    "com.google.android.soundrecorder",
    "com.miui.soundrecorder",
    "com.coloros.soundrecorder",
    "com.simplemobiletools.voicerecorder",
    "org.fossify.voicerecorder",
]

STORY_PARAGRAPHS = [
    "Brother: 'Good afternoon, there are iron smoke stains on your tie. I observe you carry something that glints like crystal in the lamplight, along with a pocket watch.' Sister: 'Ah, Mycroft. Your wooden heart still beats beneath your coat. What I carry in this vial shall bring silk-draped reunions to many families... through suit dressed gatherings in in the church.'",
    "Brother: One black shadow is cast by you and the iron lampposts across London. You hide behind crystal faces of deception, yet I see through them.' Sister: 'How poetic. You wear your silk medal from the Queen like a teacher proudly presenting a complex formula - decorative but clinging to a dying tree. My steel preparations work with the precision of a Rune Goldberg machine, unlike your government's bumbling.'",
    "Brother: 'Your schemes involve five iron gates around Oxford colleges. That Kashmir suit cannot hide the student who laughs with crystal-clear joy at others' suffering.' Sister: 'Behind that wooden clockwork you wear buttons like badges of false honour. Time falls like an overturned statue, and you check your timepieces as if it could save you from an inevitable iron coffin'.",
    "Brother: 'I see seven black horses have brought your agents to the crystal palace exhibitions. Their wooden stares reveal nothing but fear of my deathly equations.' Sister: 'Through the silk-curtained window an artist of physics observes our every move with his recipes of destruction. Your silk outbursts betray you more than any ticking chronometer in your vest pocket.'",
    "Brother: 'I hear pianos and feel the silk tension rising between us like laboratory vapour from your wooden mouth.' Sister: 'Indeed, in this dubious light, am I not an iron bear wrapped in a suit with academic gown of false civility? Your crystal spectacles cannot hide the fear behind those eyes.'",
]

QUIZ_ITEMS = [
    {
        "question": "What is the cumulative number of light tanks in team green?",
        "answer": "10",
        "paragraph": STORY_PARAGRAPHS[0],
    },
    {
        "question": "Combine all dashed lines, what number is revealed?",
        "answer": "4",
        "paragraph": STORY_PARAGRAPHS[1],
    },
    {
        "question": "What is the lowest tier played when the user is a tank destroyer?",
        "answer": "10",
        "paragraph": STORY_PARAGRAPHS[2],
    },
    {
        "question": "What is the answer to the pentominos puzzle?",
        "answer": "12",
        "paragraph": STORY_PARAGRAPHS[3],
    },
    {
        "question": "what is the answer to the mirror puzzle?",
        "answer": "1807740",
        "paragraph": STORY_PARAGRAPHS[4],
    },
]


class PhoneController:
    def __init__(self) -> None:
        self.active_device_id = PHONE_ID
        self.driver: Optional[webdriver.Remote] = None

    def run_adb(self, *args: str, device_id: Optional[str] = None) -> subprocess.CompletedProcess:
        target = device_id if device_id is not None else self.active_device_id
        cmd = ["adb"]
        if target:
            cmd.extend(["-s", target])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def list_connected_devices(self) -> list[str]:
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

    def ensure_adb_connection(self) -> str:
        connected = self.list_connected_devices()
        if PHONE_ID in connected:
            self.active_device_id = PHONE_ID
            return self.active_device_id

        subprocess.run(["adb", "connect", PHONE_ID], capture_output=True, text=True, check=False)
        time.sleep(1.0)
        connected = self.list_connected_devices()
        if PHONE_ID in connected:
            self.active_device_id = PHONE_ID
            return self.active_device_id

        if connected:
            self.active_device_id = connected[0]
            return self.active_device_id

        raise RuntimeError(
            "No ADB device found. Connect your phone via wireless debugging or USB and try again."
        )

    def connect_driver(self) -> None:
        options = UiAutomator2Options()
        options.device_name = self.active_device_id
        options.udid = self.active_device_id
        options.new_command_timeout = 300
        options.adb_exec_timeout = 60000
        options.skip_unlock = True
        self.driver = webdriver.Remote(APPIUM_SERVER, options=options)

    def unlock_phone(self, pin: str) -> None:
        if not self.driver:
            raise RuntimeError("Driver is not active")

        try:
            self.driver.press_keycode(224)
        except Exception:
            self.driver.press_keycode(26)

        time.sleep(0.5)
        self.driver.swipe(540, 1800, 540, 400, duration=800)
        time.sleep(0.6)

        digit_keycodes = {str(i): 7 + i for i in range(10)}
        for ch in pin:
            keycode = digit_keycodes.get(ch)
            if keycode is None:
                continue
            self.driver.press_keycode(keycode)
            time.sleep(0.08 + random.uniform(0.0, 0.04))

        self.driver.press_keycode(66)
        time.sleep(1.0)

    def open_voice_recorder(self) -> str:
        if not self.driver:
            raise RuntimeError("Driver is not active")

        installed = set(self._list_installed_packages())
        for package in VOICE_RECORDER_PACKAGES:
            if package not in installed:
                continue
            try:
                self.driver.activate_app(package)
                time.sleep(1.2)
                return package
            except WebDriverException:
                continue

        raise RuntimeError("Voice Recorder app not found. Add its package name to VOICE_RECORDER_PACKAGES.")

    def open_target_url(self) -> None:
        result = self.run_adb(
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            TARGET_URL,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Could not open URL: {result.stderr.strip()}")

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _list_installed_packages(self) -> list[str]:
        result = self.run_adb("shell", "pm", "list", "packages")
        packages = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.split("package:", 1)[1].strip())
        return packages


class ChallengeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ArmyRiot Challenge - Oxford Casefile")
        self.root.configure(bg="#0f2338")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", self._exit_fullscreen)
        self.root.bind("<F11>", self._toggle_fullscreen)

        self.phone = PhoneController()
        self.ui_queue = queue.Queue()
        self.quiz_cards = []
        self.quiz_visible = False
        self.desktop_visible = False
        self.desktop_bg_source = None
        self.desktop_bg_photo = None
        self.desktop_bg_item = None
        self.windows_icon_photo = None
        self.website_letter_image = None
        self.eye_hotspot_center = (0, 0)

        self.status_var = tk.StringVar(value="Esteemed Detectives, Below lies a mysterious " \
        "conversation described with cryptic clues and strange occurrences. It falls upon you " \
        "to decipher this enigma and discover the correct leads that point to the deadly weapon. " \
        "Read carefully, for the clues are masterfully concealed. Essential hints reside in the " \
        "introduction paragraph which you shall require, and after 'Follow the trail now' your " \
        "hunt begins. Do not become lost amongst the mysterious dialogue and much " \
        "success with your investigation!")

        self._build_ui()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.colors = {
            "bg_navy": "#0f2338",
            "bg_panel": "#f4efe1",
            "ink": "#1f1a17",
            "accent": "#8c6a2f",
            "accent_dark": "#5d4721",
            "status": "#2c4f77",
            "hint": "#6e4f1d",
        }

        self.outer = tk.Frame(self.root, bg=self.colors["bg_navy"], padx=28, pady=20)
        self.outer.pack(fill="both", expand=True)

        self.header = tk.Frame(self.outer, bg=self.colors["bg_navy"])
        self.header.pack(fill="x", pady=(0, 14))

        tk.Label(
            self.header,
            text="Unlock Laptop",
            font=("Georgia", 30, "bold"),
            fg="#f7f3e9",
            bg=self.colors["bg_navy"],
        ).pack(anchor="w")

        self.container = tk.Frame(
            self.outer,
            bg=self.colors["bg_panel"],
            highlightthickness=3,
            highlightbackground=self.colors["accent"],
            padx=22,
            pady=20,
        )
        self.container.pack(fill="both", expand=True)

        self.status_label = tk.Label(
            self.container,
            textvariable=self.status_var,
            font=("Cambria", 12, "bold"),
            fg=self.colors["status"],
            bg=self.colors["bg_panel"],
            pady=4,
            wraplength=980,
            justify="left",
        )
        self.status_label.pack(anchor="w")

        self.gate_frame = tk.LabelFrame(
            self.container,
            text="",
            padx=14,
            pady=12,
            font=("Cambria", 13, "bold"),
            bg=self.colors["bg_panel"],
            fg=self.colors["accent_dark"],
            highlightthickness=1,
            highlightbackground="#c5b28a",
        )
        self.gate_frame.pack(fill="x", pady=6)

        tk.Label(
            self.gate_frame,
            text=HOME_RIDDLE,
            font=("Cambria", 12),
            bg=self.colors["bg_panel"],
            fg=self.colors["ink"],
            wraplength=980,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        tk.Label(
            self.gate_frame,
            text="Login code:",
            font=("Cambria", 12),
            bg=self.colors["bg_panel"],
            fg=self.colors["ink"],
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.riddle_entry = tk.Entry(
            self.gate_frame,
            width=40,
            font=("Cambria", 12),
            bg="#fffdf6",
            fg=self.colors["ink"],
            relief="solid",
            bd=1,
            insertbackground=self.colors["ink"],
        )
        self.riddle_entry.grid(row=1, column=1, padx=10, pady=(8, 5), sticky="ew")

        self.start_btn = tk.Button(
            self.gate_frame,
            text="Login as Mycroft Holmes",
            command=self._start_riddle_check,
            font=("Cambria", 12, "bold"),
            bg=self.colors["accent"],
            fg="#fdf7ea",
            activebackground="#a67b32",
            activeforeground="#ffffff",
            relief="flat",
            padx=18,
            pady=7,
            cursor="hand2",
        )
        self.start_btn.grid(row=2, column=1, sticky="e", pady=8)
        self.gate_frame.grid_columnconfigure(1, weight=1)

        self.desktop_frame = tk.Frame(
            self.container,
            bg="#000000",
            highlightthickness=0,
        )
        self.desktop_canvas = tk.Canvas(
            self.desktop_frame,
            bg="#000000",
            highlightthickness=0,
            bd=0,
        )
        self.desktop_canvas.pack(fill="both", expand=True)

        self.website_info_frame = tk.Frame(
            self.desktop_canvas,
            bg="#000000",
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        self.website_letter_label = tk.Label(
            self.website_info_frame,
            bg="#000000",
            fg="#ffffff",
        )
        self.website_letter_label.pack(anchor="nw", fill="both", expand=True)
        self.website_info_window = self.desktop_canvas.create_window(
            26,
            26,
            window=self.website_info_frame,
            anchor="nw",
            state="hidden",
        )

        self.taskbar = tk.Frame(self.desktop_canvas, bg="#ffffff", height=TASKBAR_HEIGHT)
        self.taskbar.pack(side="bottom", fill="x")
        self.start_icon_label = tk.Label(
            self.taskbar,
            text="",
            bg="#ffffff",
            bd=0,
            padx=0,
            pady=0,
        )
        self.start_icon_label.pack(side="left", padx=(0, 8), fill="y")

        self.unlock_phone_btn = tk.Button(
            self.taskbar,
            text="Unlock Phone",
            command=self._run_unlock_phone_action,
            font=("Cambria", 10, "bold"),
            bg="#f0f0f0",
            fg="#1f1f1f",
            activebackground="#e2e2e2",
            activeforeground="#111111",
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self.unlock_phone_btn.pack(side="left", padx=(10, 0), pady=2)

        self.taskbar_status_label = tk.Label(
            self.taskbar,
            text="Mycroft Workstation",
            font=("Cambria", 10),
            bg="#ffffff",
            fg="#444444",
        )
        self.taskbar_status_label.pack(side="right", padx=10)

        self._load_windows_taskbar_icon()
        self._load_brief_letter_image()

        self.desktop_canvas.bind("<Configure>", self._on_desktop_canvas_resize)
        self.desktop_canvas.bind("<Button-1>", self._on_desktop_click)

        self.desktop_frame.pack_forget()

        self.quiz_frame = tk.LabelFrame(
            self.container,
            text="Conversations",
            padx=14,
            pady=12,
            font=("Cambria", 13, "bold"),
            bg=self.colors["bg_panel"],
            fg=self.colors["accent_dark"],
            highlightthickness=1,
            highlightbackground="#c5b28a",
        )
        self.quiz_frame.pack(fill="both", expand=True, pady=8)
        self.quiz_visible = True

        quiz_body = tk.Frame(self.quiz_frame, bg=self.colors["bg_panel"])
        quiz_body.pack(fill="both", expand=True)

        quiz_canvas = tk.Canvas(quiz_body, bg=self.colors["bg_panel"], highlightthickness=0)
        quiz_scrollbar = tk.Scrollbar(quiz_body, orient="vertical", command=quiz_canvas.yview)
        self.quiz_content = tk.Frame(quiz_canvas, bg=self.colors["bg_panel"])
        self.quiz_content.bind(
            "<Configure>",
            lambda _event: quiz_canvas.configure(scrollregion=quiz_canvas.bbox("all")),
        )
        quiz_canvas.create_window((0, 0), window=self.quiz_content, anchor="nw")
        quiz_canvas.configure(yscrollcommand=quiz_scrollbar.set)
        quiz_canvas.pack(side="left", fill="both", expand=True)
        quiz_scrollbar.pack(side="right", fill="y")

        for index, item in enumerate(QUIZ_ITEMS):
            card = tk.LabelFrame(
                self.quiz_content,
                text=f"Answer question {index + 1} to reveal the next paragraph",
                padx=12,
                pady=10,
                font=("Cambria", 12, "bold"),
                bg=self.colors["bg_panel"],
                fg=self.colors["accent_dark"],
                highlightthickness=1,
                highlightbackground="#d2c3a2",
            )
            card.pack(fill="x", pady=6)

            question_label = tk.Label(
                card,
                text=item["question"],
                wraplength=980,
                justify="left",
                font=("Cambria", 12),
                bg=self.colors["bg_panel"],
                fg=self.colors["ink"],
            )
            question_label.pack(anchor="w", fill="x")

            answer_row = tk.Frame(card, bg=self.colors["bg_panel"])
            answer_row.pack(fill="x", pady=(8, 0))

            answer_entry = tk.Entry(
                answer_row,
                width=48,
                state="normal",
                font=("Cambria", 12),
                bg="#fffdf6",
                fg=self.colors["ink"],
                relief="solid",
                bd=1,
                insertbackground=self.colors["ink"],
            )
            answer_entry.pack(side="left", fill="x", expand=True)

            submit_btn = tk.Button(
                answer_row,
                text="Submit",
                state="normal",
                command=lambda item_index=index: self._submit_answer(item_index),
                font=("Cambria", 11, "bold"),
                bg=self.colors["accent"],
                fg="#fdf7ea",
                activebackground="#a67b32",
                activeforeground="#ffffff",
                relief="flat",
                padx=14,
                pady=6,
                cursor="hand2",
            )
            submit_btn.pack(side="left", padx=(8, 0))

            paragraph_label = tk.Label(
                card,
                text=item["paragraph"],
                wraplength=980,
                justify="left",
                font=("Cambria", 12, "italic"),
                bg=self.colors["bg_panel"],
                fg=self.colors["status"],
            )

            self.quiz_cards.append(
                {
                    "frame": card,
                    "question_label": question_label,
                    "paragraph_label": paragraph_label,
                    "answer_entry": answer_entry,
                    "submit_btn": submit_btn,
                    "answer": item["answer"].strip().lower(),
                    "paragraph": item["paragraph"],
                    "attempted": False,
                    "solved": False,
                }
            )

        footer = tk.Frame(self.outer, bg=self.colors["bg_navy"])
        footer.pack(fill="x", pady=(10, 0))
        # tk.Label(
        #     footer,
        #     text="F11: toggle full-screen   |   Esc: exit full-screen",
        #     font=("Cambria", 10),
        #     fg="#ceb781",
        #     bg=self.colors["bg_navy"],
        # ).pack(anchor="e")

        self.root.bind("<Configure>", self._on_resize)

    def _load_windows_taskbar_icon(self) -> None:
        if not os.path.exists(WINDOWS_ICON_IMAGE):
            return
        try:
            if Image is not None and ImageTk is not None:
                icon = Image.open(WINDOWS_ICON_IMAGE).convert("RGBA")
                icon_size = max(1, TASKBAR_HEIGHT)
                icon = icon.resize((icon_size, icon_size), Image.LANCZOS)
                self.windows_icon_photo = ImageTk.PhotoImage(icon)
            else:
                self.windows_icon_photo = tk.PhotoImage(file=WINDOWS_ICON_IMAGE)
            self.start_icon_label.config(image=self.windows_icon_photo)
        except Exception:
            pass

    def _load_brief_letter_image(self) -> None:
        if not os.path.exists(BRIEF_MYCROFT_IMAGE):
            self.website_letter_label.config(
                text="Letter image not found.",
                font=("Cambria", 11, "italic"),
                wraplength=720,
                justify="left",
            )
            return

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(BRIEF_MYCROFT_IMAGE).convert("RGBA")
                max_width = 560
                if image.width > max_width:
                    target_height = max(1, int(image.height * (max_width / image.width)))
                    image = image.resize((max_width, target_height), Image.LANCZOS)
                self.website_letter_image = ImageTk.PhotoImage(image)
            else:
                self.website_letter_image = tk.PhotoImage(file=BRIEF_MYCROFT_IMAGE)
            self.website_letter_label.config(image=self.website_letter_image, text="")
        except Exception:
            self.website_letter_label.config(
                text="Letter image could not be loaded.",
                font=("Cambria", 11, "italic"),
                wraplength=720,
                justify="left",
            )

    def _toggle_fullscreen(self, _event: tk.Event | None = None) -> None:
        current = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not current)

    def _exit_fullscreen(self, _event: tk.Event | None = None) -> None:
        self.root.attributes("-fullscreen", False)

    def _on_resize(self, event: tk.Event) -> None:
        width = max(event.width - 120, 560)
        for card in self.quiz_cards:
            card["question_label"].config(wraplength=width)
            card["paragraph_label"].config(wraplength=width)

    def _show_quiz_panel(self) -> None:
        if self.quiz_visible:
            return
        self.quiz_frame.pack(fill="both", expand=True, pady=8)
        self.quiz_visible = True

    def _show_desktop_panel(self) -> None:
        if self.desktop_visible:
            return
        self.root.configure(bg="#000000")
        self.outer.configure(bg="#000000", padx=0, pady=0)
        self.header.pack_forget()
        self.status_label.pack_forget()
        self.container.configure(bg="#000000", highlightthickness=0, padx=0, pady=0)
        self.gate_frame.pack_forget()
        if self.quiz_visible:
            self.quiz_frame.pack_forget()
            self.quiz_visible = False
        self.desktop_frame.pack(fill="both", expand=True)
        self._refresh_desktop_background()
        self.desktop_canvas.itemconfigure(self.website_info_window, state="hidden")
        self.desktop_visible = True

    def _on_desktop_canvas_resize(self, _event: tk.Event) -> None:
        if self.desktop_visible:
            self._refresh_desktop_background()

    def _on_desktop_click(self, event: tk.Event) -> None:
        if not self.desktop_visible:
            return
        eye_x, eye_y = self.eye_hotspot_center
        dx = event.x - eye_x
        dy = event.y - eye_y
        if (dx * dx + dy * dy) <= (EYE_HOTSPOT_RADIUS_PX * EYE_HOTSPOT_RADIUS_PX):
            self._run_open_website_action()

    def _refresh_desktop_background(self) -> None:
        canvas_w = max(self.desktop_canvas.winfo_width(), 1)
        canvas_h = max(self.desktop_canvas.winfo_height(), 1)
        self.eye_hotspot_center = (
            int(canvas_w * EYE_HOTSPOT_X_RATIO),
            int(canvas_h * EYE_HOTSPOT_Y_RATIO),
        )

        if Image is not None and ImageTk is not None:
            if self.desktop_bg_source is None:
                self.desktop_bg_source = Image.open(DESKTOP_BACKGROUND_IMAGE)

            src_w, src_h = self.desktop_bg_source.size
            scale = max(canvas_w / src_w, canvas_h / src_h)
            target_w = max(1, int(src_w * scale))
            target_h = max(1, int(src_h * scale))
            resized = self.desktop_bg_source.resize((target_w, target_h), Image.LANCZOS)
            left = (target_w - canvas_w) // 2
            top = (target_h - canvas_h) // 2
            cropped = resized.crop((left, top, left + canvas_w, top + canvas_h))
            self.desktop_bg_photo = ImageTk.PhotoImage(cropped)
        else:
            self.desktop_bg_photo = tk.PhotoImage(file=DESKTOP_BACKGROUND_IMAGE)

        if self.desktop_bg_item is None:
            self.desktop_bg_item = self.desktop_canvas.create_image(
                canvas_w // 2,
                canvas_h // 2,
                image=self.desktop_bg_photo,
                anchor="center",
            )
        else:
            self.desktop_canvas.itemconfig(self.desktop_bg_item, image=self.desktop_bg_photo)
            self.desktop_canvas.coords(self.desktop_bg_item, canvas_w // 2, canvas_h // 2)
        self.desktop_canvas.tag_lower(self.desktop_bg_item)

    def _start_riddle_check(self) -> None:
        answer = self.riddle_entry.get().strip().lower()

        if answer != HOME_RIDDLE_ANSWER.strip().lower():
            messagebox.showerror("Incorrect", "That answer is not correct. Read the riddle again.")
            return

        self.start_btn.config(state="disabled")
        self.riddle_entry.config(state="disabled")
        self.status_var.set("Riddle solved. Workstation unlocked. Choose your action.")
        self._show_desktop_panel()

    def _run_unlock_phone_action(self) -> None:
        self.unlock_phone_btn.config(state="disabled")
        threading.Thread(target=self._unlock_phone_flow, daemon=True).start()

    def _run_open_website_action(self) -> None:
        threading.Thread(target=self._open_website_flow, daemon=True).start()

    def _unlock_phone_flow(self) -> None:
        try:
            if not os.path.exists(PHONE_FLOW_SCRIPT):
                raise RuntimeError(f"Phone flow script not found: {PHONE_FLOW_SCRIPT}")

            self.ui_queue.put(("status", "Running phone_notes_then_open_link.py..."))
            result = subprocess.run(
                [sys.executable, PHONE_FLOW_SCRIPT],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                details = stderr or stdout or "Unknown error"
                raise RuntimeError(f"phone_notes_then_open_link.py failed: {details}")

            self.ui_queue.put(("status", "phone_notes_then_open_link.py completed."))
        except subprocess.TimeoutExpired:
            self.ui_queue.put(("error", "phone_notes_then_open_link.py timed out after 120 seconds."))
        except Exception as exc:
            self.ui_queue.put(("error", str(exc)))
        finally:
            self.ui_queue.put(("unlock_done", ""))

    def _open_website_flow(self) -> None:
        try:
            self.ui_queue.put(("show_website_link", ""))
            self.ui_queue.put(("status", "Website link shown on screen."))
        except Exception as exc:
            self.ui_queue.put(("error", str(exc)))

    def _enable_quiz_cards(self) -> None:
        for card in self.quiz_cards:
            if card["solved"]:
                continue
            card["answer_entry"].config(state="normal")
            card["submit_btn"].config(state="normal")

    def _submit_answer(self, item_index: int) -> None:
        card = self.quiz_cards[item_index]
        if card["attempted"]:
            return

        card["attempted"] = True
        answer = card["answer_entry"].get().strip().lower()
        card["answer_entry"].config(state="disabled")
        card["submit_btn"].config(state="disabled")

        if answer != card["answer"]:
            messagebox.showwarning("Not yet", "That answer is not correct. You only get one try on each question.")
            return

        self._unlock_paragraph(item_index)

    def _unlock_paragraph(self, item_index: int) -> None:
        card = self.quiz_cards[item_index]
        card["solved"] = True
        card["answer_entry"].delete(0, tk.END)
        card["question_label"].pack_forget()
        card["paragraph_label"].pack(anchor="w", fill="x")
        card["frame"].config(text=f"Paragraph {item_index + 1} unlocked")

        if all(quiz_card["solved"] for quiz_card in self.quiz_cards):
            self.status_var.set("All five paragraphs are unlocked. Opening the website on your phone...")
            threading.Thread(target=self._open_final_website, daemon=True).start()

    def _open_final_website(self) -> None:
        try:
            self.phone.open_target_url()
            self.ui_queue.put(("status", "Done. The website is now open on your phone."))
            self.ui_queue.put(("done", ""))
        except Exception as exc:
            self.ui_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "error":
                    self.status_var.set("An error occurred.")
                    messagebox.showerror("Error", payload)
                    self.start_btn.config(state="normal")
                    self.riddle_entry.config(state="normal")
                elif kind == "quiz_ready":
                    self._enable_quiz_cards()
                elif kind == "done":
                    messagebox.showinfo("Success", "Challenge complete. Website opened.")
                elif kind == "unlock_done":
                    self.unlock_phone_btn.config(state="normal")
                elif kind == "show_website_link":
                    self.desktop_canvas.itemconfigure(self.website_info_window, state="normal")
        except queue.Empty:
            pass

        self.root.after(120, self._poll_queue)

    def _on_close(self) -> None:
        self.phone.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = ChallengeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
