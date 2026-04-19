# -*- coding: utf-8 -*-
# Rock Identification Key GUI (GR/EN)
# GUI improved only. Decision tree and rock logic kept unchanged.

import os
import tkinter as tk
from tkinter import ttk
import webbrowser
from CUT_Rock_key_data import (
    APP_LINK,
    ORIGINAL_LINK,
    WIKI_LINKS,
    ROCK_INFO_EN,
    ROCK_INFO_EL,
    NODES_EN,
    NODES_EL,
    UI_STR,
)


# -------------------- App --------------------
class RockKeyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.nodes = {"el": NODES_EL, "en": NODES_EN}
        self.rocks = {"el": ROCK_INFO_EL, "en": ROCK_INFO_EN}
        self.title(UI_STR[self.lang]["title"])
        self.geometry("1180x760")
        self.minsize(980, 680)
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass
        self.configure(bg="#eef3f8")

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TFrame", background="#eef3f8")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background="#eef3f8")
        self.style.configure("Body.TLabel", font=("Segoe UI", 11), background="#ffffff")
        self.style.configure("TitleCard.TLabel", font=("Segoe UI", 12, "bold"), background="#ffffff")
        self.style.configure("Question.TLabel", font=("Segoe UI", 16, "bold"), background="#ffffff", wraplength=520)
        self.style.configure("Explain.TLabel", font=("Segoe UI", 11), foreground="#4b5b6b", background="#ffffff", wraplength=520)
        self.style.configure("Rock.TLabel", font=("Segoe UI", 18, "bold"), background="#ffffff")

        self.history = []
        self.current = "1"
        self._current_photo = None
        self._logo_photo = None
        self._home_photo = None

        self.create_menu()
        self.create_widgets()
        self.show_node(self.current)

    def create_menu(self):
        menubar = tk.Menu(self)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label=UI_STR[self.lang]["help_defs"], command=self.show_glossary)
        helpmenu.add_separator()
        helpmenu.add_command(label=UI_STR[self.lang]["about"], command=self.show_about)
        menubar.add_cascade(label=UI_STR[self.lang]["help_menu"], menu=helpmenu)
        self.config(menu=menubar)

    def create_widgets(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        self.top_card = tk.Frame(outer, bg="#14324a", bd=0, padx=18, pady=10)
        self.top_card.pack(fill="x", pady=(0, 12))

        header_row = tk.Frame(self.top_card, bg="#14324a")
        header_row.pack(fill="x", pady=(0, 8))

        left_header = tk.Frame(header_row, bg="#14324a")
        left_header.pack(fill="x", anchor="nw")

        logo = self._load_logo()
        self.logo_label = tk.Label(left_header, bg="#14324a")
        if logo:
            self.logo_label.configure(image=logo)
            self.logo_label.image = logo
        self.logo_label.pack(side="left", anchor="nw", padx=(0, 12))

        text_header = tk.Frame(left_header, bg="#14324a")
        text_header.pack(side="left", fill="x", expand=True, anchor="nw")

        self.top_title = tk.Label(
            text_header,
            text=UI_STR[self.lang]["intro_title"],
            fg="white",
            bg="#14324a",
            font=("Segoe UI", 20, "bold"),
            anchor="w"
        )
        self.top_title.pack(fill="x", anchor="w")

        self.top_desc = tk.Label(
            text_header,
            text=UI_STR[self.lang]["intro_body"],
            fg="#dce9f5",
            bg="#14324a",
            justify="left",
            wraplength=700,
            font=("Segoe UI", 10),
            anchor="w"
        )
        self.top_desc.pack(fill="x", pady=(4, 0), anchor="w")

        controls_row = tk.Frame(self.top_card, bg="#14324a")
        controls_row.pack(fill="x", pady=(2, 0))

        right_group = tk.Frame(controls_row, bg="#14324a")
        right_group.pack(side="right", anchor="e")

        tk.Label(
            right_group,
            text=UI_STR[self.lang]["lang_label"],
            fg="white",
            bg="#14324a",
            font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=(0, 8))

        self.lang_sel = ttk.Combobox(
            right_group,
            values=["English", "Ελληνικά"],
            state="readonly",
            width=12
        )
        self.lang_sel.set("English")
        self.lang_sel.bind("<<ComboboxSelected>>", self.on_lang_change)
        self.lang_sel.pack(side="left", padx=(0, 16))

        self.home_button = tk.Label(right_group, bg="#14324a", cursor="hand2")
        home_img = self._load_home_image()
        if home_img:
            self.home_button.configure(image=home_img)
            self.home_button.image = home_img
        else:
            self.home_button.configure(
                text=UI_STR[self.lang]["portal"],
                fg="white",
                bg="#14324a",
                font=("Segoe UI", 10, "bold")
            )
        self.home_button.pack(side="left")
        self.home_button.bind("<Button-1>", lambda e: webbrowser.open(APP_LINK))

        top_buttons = tk.Frame(self.top_card, bg="#14324a")
        top_buttons.pack(fill="x", pady=(6, 0))

        self.original_btn = tk.Button(
            top_buttons,
            text=UI_STR[self.lang]["orig_btn"],
            command=lambda: webbrowser.open(ORIGINAL_LINK),
            bg="#f6c344",
            fg="#17212b",
            activebackground="#ffd466",
            relief="flat",
            padx=14,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        self.original_btn.pack(side="left")

        self.about_btn = tk.Button(
            top_buttons,
            text=UI_STR[self.lang]["about"],
            command=self.show_about,
            bg="#ffffff",
            fg="#14324a",
            activebackground="#f1f5f9",
            relief="flat",
            padx=14,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        self.about_btn.pack(side="left", padx=(10, 0))

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg="#ffffff", bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right = tk.Frame(main, bg="#ffffff", bd=1, relief="solid")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Label(left, text=UI_STR[self.lang]["questions_header"], bg="#ffffff", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.question = ttk.Label(left, text="", style="Question.TLabel", justify="left")
        self.question.pack(fill="x", padx=18, pady=(0, 8))
        self.explain = ttk.Label(left, text="", style="Explain.TLabel", justify="left")
        self.explain.pack(fill="x", padx=18, pady=(0, 16))

        self.yes_btn = tk.Button(left, text="", command=lambda: self.answer(True), bg="#1ea672", fg="white", activebackground="#24bb80", relief="flat", wraplength=480, justify="left", anchor="w", padx=14, pady=12, font=("Segoe UI", 11, "bold"), cursor="hand2")
        self.yes_btn.pack(fill="x", padx=18, pady=(0, 10))

        self.no_btn = tk.Button(left, text="", command=lambda: self.answer(False), bg="#d9544f", fg="white", activebackground="#e56a65", relief="flat", wraplength=480, justify="left", anchor="w", padx=14, pady=12, font=("Segoe UI", 11, "bold"), cursor="hand2")
        self.no_btn.pack(fill="x", padx=18, pady=(0, 14))

        nav = tk.Frame(left, bg="#ffffff")
        nav.pack(fill="x", padx=18, pady=(0, 12))
        self.back_btn = tk.Button(nav, text=UI_STR[self.lang]["back"], command=self.go_back, bg="#eaf0f6", fg="#1a2c3b", relief="flat", padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.back_btn.pack(side="left", padx=(0, 8))
        self.reset_btn = tk.Button(nav, text=UI_STR[self.lang]["home"], command=self.go_home, bg="#eaf0f6", fg="#1a2c3b", relief="flat", padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.reset_btn.pack(side="left", padx=(0, 8))
        self.info_btn = tk.Button(nav, text=UI_STR[self.lang]["info"], command=self.show_rock_info, state="disabled", bg="#7d5cff", fg="white", relief="flat", padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.info_btn.pack(side="left", padx=(0, 8))
        self.wiki_btn = tk.Button(nav, text=UI_STR[self.lang]["wiki"], command=self.open_wikipedia, state="disabled", bg="#4f7cff", fg="white", relief="flat", padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.wiki_btn.pack(side="left")

        self.note = tk.Label(left, text=UI_STR[self.lang]["note"], bg="#ffffff", fg="#5b6773", justify="left", wraplength=520, font=("Segoe UI", 10, "italic"))
        self.note.pack(fill="x", padx=18, pady=(0, 18))

        tk.Label(right, text=UI_STR[self.lang]["result_header"], bg="#ffffff", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.result_label = ttk.Label(right, text="", style="Rock.TLabel", justify="left")
        self.result_label.pack(anchor="w", padx=18, pady=(0, 10))
        self.img_label = tk.Label(right, bg="#ffffff")
        self.img_label.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _load_logo(self):
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None

        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        candidates = [
            os.path.join(base_dir, "university_logo.png"),
            os.path.join(base_dir, "university_logo.jpg"),
            os.path.join(base_dir, "university_logo.jpeg"),
            os.path.join(base_dir, "logo.png"),
            os.path.join(base_dir, "logo.jpg"),
            os.path.join(base_dir, "logo.jpeg"),
        ]
        for p in candidates:
            if os.path.exists(p):
                im = Image.open(p)
                im = im.resize((180, 60), Image.LANCZOS)
                self._home_photo = ImageTk.PhotoImage(im)
                return self._home_photo
        return None

    def _load_home_image(self):
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None

        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        candidates = [
            os.path.join(base_dir, "home.png"),
            os.path.join(base_dir, "home.jpg"),
            os.path.join(base_dir, "home.jpeg"),
        ]
        for p in candidates:
            if os.path.exists(p):
                im = Image.open(p)
                w, h = im.size
                target_h = 56
                target_w = int(w * target_h / h)
                im = im.resize((target_w, target_h), Image.LANCZOS)
                self._home_photo = ImageTk.PhotoImage(im)
                return self._home_photo
        return None

    def _load_result_image(self, rock_id):
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None

        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        candidates = [
            os.path.join(base_dir, rock_id + ".jpg"),
            os.path.join(base_dir, rock_id + ".jpeg"),
            os.path.join(base_dir, rock_id + ".png"),
            os.path.join(base_dir, rock_id.lower() + ".jpg"),
            os.path.join(base_dir, rock_id.lower() + ".jpeg"),
            os.path.join(base_dir, rock_id.lower() + ".png"),
            os.path.join(base_dir, rock_id.capitalize() + ".jpg"),
            os.path.join(base_dir, rock_id.capitalize() + ".jpeg"),
            os.path.join(base_dir, rock_id.capitalize() + ".png"),
        ]
        for p in candidates:
            if os.path.exists(p):
                im = Image.open(p)
                im.thumbnail((470, 360))
                return ImageTk.PhotoImage(im)
        return None

    def show_node(self, node_id):
        self.current = node_id
        ui = UI_STR[self.lang]
        nodes = self.nodes[self.lang]
        rocks = self.rocks[self.lang]

        self.info_btn.configure(state="disabled")
        self.wiki_btn.configure(state="disabled")
        self.result_label.configure(text="")

        if node_id in rocks:
            rock = rocks[node_id]
            self.question.configure(text="")
            self.explain.configure(text="")
            self.yes_btn.configure(state="disabled", text=ui["yes"])
            self.no_btn.configure(state="disabled", text=ui["no"])
            self.info_btn.configure(state="normal")
            self.wiki_btn.configure(state="normal")
            self.result_label.configure(text=f"{rock.get('name', node_id)}  —  {rock['type']}")
            photo = self._load_result_image(node_id)
            if photo:
                self._current_photo = photo
                self.img_label.configure(image=photo, text="")
            else:
                self.img_label.configure(image="", text=ui["img_missing"], fg="#5b6773", font=("Segoe UI", 11), justify="center")
            return

        node = nodes[node_id]
        self.question.configure(text=node.get("text", ""))
        self.explain.configure(text=node.get("explanation", ""))
        self.img_label.configure(image="", text="")

        yes_target = node.get("yes")
        no_target = node.get("no")
        yes_text = node.get("yes_text", "")
        no_text = node.get("no_text", "")

        def btn_text(label, text):
            return f"{label}  {text}" if text else label

        self.yes_btn.configure(state="normal", text=btn_text(ui["yes"], yes_text))
        self.no_btn.configure(state="normal", text=btn_text(ui["no"], no_text))

    def answer(self, is_yes):
        if self.current in self.rocks[self.lang]:
            return
        node = self.nodes[self.lang][self.current]
        next_id = node["yes"] if is_yes else node["no"]
        self.history.append(self.current)
        self.show_node(next_id)

    def go_back(self):
        if self.history:
            self.show_node(self.history.pop())

    def go_home(self):
        self.history.clear()
        self.show_node("1")

    def show_rock_info(self):
        if self.current not in self.rocks[self.lang]:
            return
        rock = self.rocks[self.lang][self.current]
        ui = UI_STR[self.lang]
        text = ui["info_text"].format(
            name=rock.get("name", self.current),
            type=rock["type"],
            minerals=rock["minerals"],
            look=rock["look"],
            formation=rock["formation"],
            compare=rock["compare"],
        )
        RockDialog(self, rock.get("name", self.current), text)

    def open_wikipedia(self):
        if self.current not in self.rocks[self.lang]:
            return
        url = self.rocks[self.lang][self.current].get("link")
        if url:
            webbrowser.open(url)

    def show_glossary(self):
        RockDialog(self, UI_STR[self.lang]["help_defs"], UI_STR[self.lang]["gloss"])
    def show_about(self):
        if self.lang == "el":
            text = (
                "Dr Lysandros Pantelidis\n"
                "Cyprus University of Technology\n"
                "Department of Civil Engineering and Geomatics\n\n"
                "Rock Identification Key GUI\n"
                "Version 1.0\n"
                "Educational tool\n\n"
                "Το πρόγραμμα προσφέρει μόνο web app και exe έκδοση του "
                "The Rock Identification Key - by Don Peck.\n"
                "Δεν αλλάζει τον αλγόριθμο ταυτοποίησης."
            )
        else:
            text = (
                "Dr Lysandros Pantelidis\n"
                "Cyprus University of Technology\n"
                "Department of Civil Engineering and Geomatics\n\n"
                "Rock Identification Key GUI\n"
                "Version 1.0\n"
                "Educational tool\n\n"
                "This program only offers a web app and an exe version of "
                "The Rock Identification Key - by Don Peck.\n"
                "It does not change the identification algorithm."
            )
        RockDialog(self, UI_STR[self.lang]["about"], text)
        
    def on_lang_change(self, event=None):
        self.lang = "el" if self.lang_sel.get().startswith("Ε") else "en"
        ui = UI_STR[self.lang]
        self.title(ui["title"])
        self.create_menu()
        self.top_title.configure(text=ui["intro_title"])
        self.top_desc.configure(text=ui["intro_body"])
        self.original_btn.configure(text=ui["orig_btn"])
        self.about_btn.configure(text=ui["about"])
        if not getattr(self.home_button, "image", None):
            self.home_button.configure(text=ui["portal"])
        self.back_btn.configure(text=ui["back"])
        self.reset_btn.configure(text=ui["home"])
        self.info_btn.configure(text=ui["info"])
        self.wiki_btn.configure(text=ui["wiki"])
        self.note.configure(text=ui["note"])
        self.show_node(self.current)

class RockDialog(tk.Toplevel):
    def __init__(self, master, title, text):
        super().__init__(master)
        self.title(title)
        self.geometry("760x560")
        self.minsize(560, 420)
        self.transient(master)
        self.grab_set()
        txt = tk.Text(self, wrap="word", font=("Segoe UI", 11))
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Button(self, text=UI_STR[master.lang]["close"], command=self.destroy, bg="#eaf0f6", relief="flat", padx=12, pady=8, font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))

if __name__ == "__main__":
    app = RockKeyApp()
    app.mainloop()
