import asyncio
import threading
from datetime import datetime, timedelta
import customtkinter as ctk
from tkinter import filedialog, messagebox

from config.settings import COUNTIES_BY_STATE, PRESET_RANGES
from core.scraper import run_scraper, run_multi_county_scraper

class DateRangeSelector(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Real Foreclosure Scraper")
        self.geometry("600x700")
        ctk.set_appearance_mode("dark")

        self.folder_path_var = ctk.StringVar()
        ctk.CTkLabel(self, text="Save Location:").pack(pady=(10, 0))

        folder_frame = ctk.CTkFrame(self)
        folder_frame.pack(pady=5, padx=20, fill="x")

        self.folder_entry = ctk.CTkEntry(folder_frame, textvariable=self.folder_path_var, placeholder_text="Select folder...")
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.browse_button = ctk.CTkButton(folder_frame, text="Browse", command=self.browse_folder)
        self.browse_button.pack(side="right")

        self.county_var = ctk.StringVar(value="Select County")
        ctk.CTkLabel(self, text="County:").pack(pady=(10, 0))
        self.county_dropdown = ctk.CTkOptionMenu(
            self,
            values=[f"{state} - {county}" for state, counties in COUNTIES_BY_STATE.items() for county in counties],
            variable=self.county_var
        )
        self.county_dropdown.pack(pady=5)

        self.preset_var = ctk.StringVar(value="Custom Range")
        ctk.CTkLabel(self, text="Preset Date Range:").pack(pady=(10, 0))
        self.preset_dropdown = ctk.CTkOptionMenu(
            self,
            values=["Custom Range"] + list(PRESET_RANGES.keys()),
            variable=self.preset_var,
            command=self.update_dates_from_preset
        )
        self.preset_dropdown.pack(pady=5)

        self.start_date_var = ctk.StringVar()
        self.end_date_var = ctk.StringVar()

        ctk.CTkLabel(self, text="Start Date (YYYY-MM-DD):").pack(pady=(10, 0))
        self.start_entry = ctk.CTkEntry(self, textvariable=self.start_date_var, placeholder_text="YYYY-MM-DD")
        self.start_entry.pack(pady=5)

        ctk.CTkLabel(self, text="End Date (YYYY-MM-DD):").pack(pady=(10, 0))
        self.end_entry = ctk.CTkEntry(self, textvariable=self.end_date_var, placeholder_text="YYYY-MM-DD")
        self.end_entry.pack(pady=5)

        self.headless_var = ctk.BooleanVar(value=False)
        self.headless_checkbox = ctk.CTkCheckBox(
            self,
            text="Run Browser in Headless Mode",
            variable=self.headless_var
        )
        self.headless_checkbox.pack(pady=10)

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        self.progress_label = ctk.CTkLabel(self, text="Waiting to start...")
        self.progress_label.pack(pady=5)

        self.submit_button = ctk.CTkButton(self, text="Confirm Selection", command=self.submit_selection)
        self.submit_button.pack(pady=10)

        ctk.CTkLabel(self, text="Log Output:").pack(pady=(10, 0))
        self.log_textbox = ctk.CTkTextbox(self, height=120, wrap="word")
        self.log_textbox.pack(pady=5, padx=20, fill="both", expand=True)
        self.log_textbox.configure(state="disabled")

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_var.set(folder_selected)

    def update_dates_from_preset(self, preset_name):
        if preset_name == "Custom Range":
            return
        today = datetime.today()
        days_to_add = PRESET_RANGES[preset_name]
        self.start_date_var.set(today.strftime("%Y-%m-%d"))
        self.end_date_var.set((today + timedelta(days=days_to_add)).strftime("%Y-%m-%d"))

    def submit_selection(self):
        county = self.county_var.get().split(":")[-1].strip()
        start_date_str = self.start_date_var.get().strip()
        end_date_str = self.end_date_var.get().strip()
        headless_mode = self.headless_var.get()

        if county == "Select County":
            messagebox.showerror("Error", "Please select a county")
            return
        self.submit_button.configure(state="disabled")

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            if start_date > end_date:
                raise ValueError("Start date must be before end date")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
            return

        parts = county.split("-")
        if len(parts) > 2:
            state = parts[0].strip()
            county = f"{parts[1].strip()}-{parts[2].strip()}"
        else:
            state = parts[0].strip()
            county = parts[1].strip()

        self.selection_data = {
            "state": state,
            "county": county,
            "start_date": start_date,
            "end_date": end_date,
            "output_file": self.folder_path_var.get(),
            "headless": headless_mode
        }

        def background_task():
            asyncio.run(run_scraper(self.selection_data, self))

        threading.Thread(target=background_task, daemon=True).start()

def create_multi_county_gui():
    window = ctk.CTk()
    window.title("Real Foreclosure Scraper")
    window.geometry("650x890")
    ctk.set_appearance_mode("dark")

    selected_data = {}
    county_vars = {}

    folder_var = ctk.StringVar()
    ctk.CTkLabel(window, text="Save Location:").pack(pady=(10, 0))
    folder_frame = ctk.CTkFrame(window)
    folder_frame.pack(pady=5, padx=20, fill="x")

    folder_entry = ctk.CTkEntry(folder_frame, textvariable=folder_var)
    folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

    def browse():
        folder = filedialog.askdirectory()
        if folder:
            folder_var.set(folder)

    ctk.CTkButton(folder_frame, text="Browse", command=browse).pack(side="right")

    ctk.CTkLabel(window, text="Select Counties:").pack(pady=(10, 0))
    county_frame = ctk.CTkScrollableFrame(window, height=250)
    county_frame.pack(pady=5, padx=20, fill="both", expand=True)

    COLUMNS = 3
    current_row = 0

    for state, counties in COUNTIES_BY_STATE.items():
        state_label = ctk.CTkLabel(county_frame, text=f"{state}:", font=("Arial", 11, "bold"))
        state_label.grid(row=current_row, column=0, columnspan=COLUMNS, sticky="w", pady=(10, 2), padx=5)
        current_row += 1

        for i, county in enumerate(counties):
            row = current_row + (i // COLUMNS)
            col = i % COLUMNS
            var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(county_frame, text=county, variable=var)
            checkbox.grid(row=row, column=col, sticky="w", padx=15, pady=2)
            county_vars[f"{state}-{county}"] = var

        current_row += (len(counties) + COLUMNS - 1) // COLUMNS

    btn_frame = ctk.CTkFrame(window)
    btn_frame.pack(pady=5)

    def select_all():
        for var in county_vars.values():
            var.set(True)

    def deselect_all():
        for var in county_vars.values():
            var.set(False)

    ctk.CTkButton(btn_frame, text="Select All", command=select_all, width=100).pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="Deselect All", command=deselect_all, width=100).pack(side="left", padx=5)

    preset_var = ctk.StringVar(value="Custom Range")
    ctk.CTkLabel(window, text="Preset Date Range:").pack(pady=(10, 0))

    start_var = ctk.StringVar()
    end_var = ctk.StringVar()

    def update_dates_from_preset(choice):
        if choice == "Custom Range":
            return
        today = datetime.today()
        days = PRESET_RANGES[choice]
        start_var.set(today.strftime("%Y-%m-%d"))
        end_var.set((today + timedelta(days=days)).strftime("%Y-%m-%d"))

    ctk.CTkOptionMenu(
        window,
        values=["Custom Range"] + list(PRESET_RANGES.keys()),
        variable=preset_var,
        command=update_dates_from_preset
    ).pack(pady=5)

    date_frame = ctk.CTkFrame(window)
    date_frame.pack(pady=10, padx=20, fill="x")

    start_frame = ctk.CTkFrame(date_frame, fg_color="transparent")
    start_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
    ctk.CTkLabel(start_frame, text="Start Date (YYYY-MM-DD):").pack(pady=(0, 5))
    ctk.CTkEntry(start_frame, textvariable=start_var, placeholder_text="YYYY-MM-DD").pack(fill="x")

    end_frame = ctk.CTkFrame(date_frame, fg_color="transparent")
    end_frame.pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(end_frame, text="End Date (YYYY-MM-DD):").pack(pady=(0, 5))
    ctk.CTkEntry(end_frame, textvariable=end_var, placeholder_text="YYYY-MM-DD").pack(fill="x")

    headless_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(window, text="Run Browser in Headless Mode", variable=headless_var).pack(pady=10)

    progress_bar = ctk.CTkProgressBar(window, width=500)
    progress_bar.set(0)
    progress_bar.pack(pady=10)

    progress_label = ctk.CTkLabel(window, text="Waiting to start...")
    progress_label.pack(pady=5)

    ctk.CTkLabel(window, text="Log Output:").pack(pady=(10, 0))
    log_box = ctk.CTkTextbox(window, height=100, wrap="word")
    log_box.pack(pady=5, padx=20, fill="both", expand=True)
    log_box.configure(state="disabled")

    window.progress_bar = progress_bar
    window.progress_label = progress_label
    window.log_textbox = log_box

    def submit():
        selected_counties = []
        for key, var in county_vars.items():
            if var.get():
                state, county = key.split("-", 1)
                selected_counties.append((state, county))

        if not selected_counties:
            messagebox.showerror("Error", "Select at least one county")
            return

        if not folder_var.get():
            messagebox.showerror("Error", "Select save location")
            return

        try:
            start_date = datetime.strptime(start_var.get(), "%Y-%m-%d")
            end_date = datetime.strptime(end_var.get(), "%Y-%m-%d")
            if start_date > end_date:
                raise ValueError("Start must be before end")
        except Exception:
            messagebox.showerror("Error", "Invalid dates")
            return

        selected_data['counties'] = selected_counties
        selected_data['start_date'] = start_date
        selected_data['end_date'] = end_date
        selected_data['output_file'] = folder_var.get()
        selected_data['headless'] = headless_var.get()

        submit_btn.configure(state="disabled")

        def run_async():
            asyncio.run(run_multi_county_scraper(selected_data, window))

        threading.Thread(target=run_async, daemon=True).start()

    submit_btn = ctk.CTkButton(window, text="Start Scraping", command=submit, height=40)
    submit_btn.pack(pady=10)

    window.mainloop()