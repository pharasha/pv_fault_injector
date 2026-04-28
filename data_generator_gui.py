import customtkinter as ctk
import tkinter
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
import tkintermapview
import pvlib
import json
from tkcalendar import DateEntry,Calendar
import copy
import secrets
import ast
from src.WeatherModel import WeatherModel
from src.Simulation import Simulation

# --- Theme Setup ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- Constants ---



COMM_DIR = "./data"


SYSTEM_PROPERTIES_DATA = {
    "latitude":           {"default": None,                                          "min": -90.0,  "max": 90.0,   "type": float},
    "longitude":          {"default": None,                                          "min": -180.0, "max": 180.0,  "type": float},
    "module_cec":         {"default": "Canadian_Solar_Inc__CS6X_305P",               "min": None,   "max": None,   "type": str},
    "inverter_cec":       {"default": "Fronius_USA__Fronius_Primo_3_8_1_208_240__208V_", "min": None, "max": None, "type": str},
    "altitude_m":         {"default": 470,                                           "min": 0,      "max": 9000,   "type": int},
    "tilt_deg":           {"default": 20.0,                                            "min": 0,      "max": 90,     "type": float},
    "azimuth_deg":        {"default": 180.0,                                           "min": 0,      "max": 360,    "type": float},
    "modules_per_string": {"default": 4,                                             "min": 1,      "max": 100,    "type": int},
    "strings":            {"default": 2,                                             "min": 1,      "max": 100,    "type": int},
}

TEMPORARY_EVENTS_DATA = {
    "open_string": {
        "params": {
            "strings_lost": {"default": 1, "min": 1, "max": 10, "type": int},
        }
    },
    "inverter_fault": {
        "params": {
            "efficiency_loss": {"default": 0.5, "min": 0.0, "max": 1.0, "type": float},
        }
    },
}

PERMANENT_EVENTS_DATA = {
    "soiling": {
        "enabled": True,
        "params": {
            "soiling_loss_rate":  {"default": 0.1,  "min": 0.0,  "max": 1.0,  "type": float},
            "cleaning_threshold": {"default": 0.05, "min": 0.0,  "max": 1.0,  "type": float},
            "max_soiling":        {"default": 0.5,  "min": 0.0,  "max": 1.0,  "type": float},
            "grace_period":       {"default": 7,    "min": 0,    "max": 365,  "type": int},
        }
    },
    "mask_shading": {
        "enabled": True,
        "params": {
            "az_range":           {"default": [39.0, 150.0], "min": [0.0,0.0],  "max": [360.0,360.0], "type": [float,float]},
            "el_range":           {"default": [5.0, 45.0], "min": [0.0,0.0],  "max": [90.0,90.0],  "type": [float,float]},
            "affected_fraction":  {"default": 0.3,  "min": 0.0,  "max": 1.0,   "type": float},
            "opacity":            {"default": 1.0,  "min": 0.0,  "max": 1.0,   "type": float},
            "ramp":               {"default": 0,    "min": 0,    "max": 100,   "type": int},
        }
    },
    "degradation": {
        "enabled": True,
        "params": {
            "annual_rate":        {"default": 0.5,  "min": 0.0,  "max": 5.0,  "type": float},
            "initial_years":      {"default": 0,    "min": 0,    "max": 50,   "type": int},
        }
    },
    "pid": {
        "enabled": True,
        "params": {
            "severity":           {"default": 0.5,  "min": 0.0,  "max": 1.0,  "type": float},
        }
    },
}

CEC_MODULES = list(pvlib.pvsystem.retrieve_sam('cecmod').columns)
CEC_INVERTERS = list(pvlib.pvsystem.retrieve_sam('CECInverter').columns)



# ---- Global Variables ------

# Community
comm_loaded=False
comm_file_path=""
community_name=""
community_description=""
community_start_day=""
community_end_day=""


# Systems
all_markers = []
selected_marker = None
system_counter = 0

#Functions
ignore_click = False
properties_widgets = {}
perm_events_widgets = {}



# --- Accessory Functions ------

def open_calendar_popup(entry_widget):
    """Opens a floating calendar popup and sets selected date into the entry."""
    popup = tkinter.Toplevel()
    popup.title("Pick a Date")
    popup.resizable(False, False)
    popup.grab_set()

    # ── Pre-select the already entered date if present ─────────────────────────
    current = entry_widget.get().strip()
    try:
        parsed = datetime.strptime(current, "%Y-%m-%d")
        init_kwargs = {"year": parsed.year, "month": parsed.month, "day": parsed.day}
    except ValueError:
        init_kwargs = {}  # fallback to today if empty or invalid

    cal = Calendar(
        popup,
        selectmode="day",
        date_pattern="yyyy-mm-dd",
        background="#1e2a3a",
        foreground="#ffffff",
        bordercolor="#2e3f55",
        headersbackground="#16213a",
        headersforeground="#aab4c8",
        selectbackground="#3b82f6",
        selectforeground="#ffffff",
        normalbackground="#1e2a3a",
        normalforeground="#ffffff",
        weekendbackground="#1e2a3a",
        weekendforeground="#aab4c8",
        othermonthbackground="#16213a",
        othermonthforeground="#555f70",
        **init_kwargs,  # ← injects year/month/day if a valid date was found
    )
    cal.pack(padx=10, pady=10)

    def confirm():
        entry_widget.configure(state="normal")
        entry_widget.delete(0, "end")
        entry_widget.insert(0, cal.get_date())
        entry_widget.configure(state="readonly")
        popup.destroy()

    ctk.CTkButton(popup, text="Select", command=confirm).pack(pady=(0, 10))

    popup.wait_window()
    return cal.get_date()


def format_key(s):
    return s.replace("_", " ").title()

def unformat_key(s):
    return s.replace(" ", "_").lower()


def runSim():
    # CHECK FOR ALL DATES TO BE INSIDE SIMULATION DATE
    community_dict = stateToDict()
    wm = WeatherModel()
    sim = Simulation(community_dict, wm)
    sim.run()



def debug_print():
    print(community_start_day,community_end_day)

def stateToDict():
    global all_markers,community_name,community_description,community_start_day,community_end_day
    full_dict = {}
    full_dict["name"]=unformat_key(community_name)
    full_dict["desc"]=community_description
    full_dict["start_date"]=community_start_day
    full_dict["end_date"]=community_end_day
    full_dict["systems"]=[]
    for marker in all_markers:
        sys_dict={}
        sys_dict["name"]=marker.text
        sys_dict["props"]={}
        sys_dict["props"]=marker.props
        sys_dict["events"]={}
        sys_dict["events"]["permanent"]=marker.perm_events
        sys_dict["events"]["temporary"]=marker.temp_events
        full_dict["systems"].append(sys_dict)
    return full_dict


def switchColors(marker, marker_color_circle="#2ecc71", marker_color_outside="#27ae60"):
    map_widget.canvas.itemconfig(marker.polygon, fill=marker_color_outside, outline=marker_color_outside)
    map_widget.canvas.itemconfig(marker.big_circle, fill=marker_color_circle, outline=marker_color_outside)

# -------------------  Community Tools

def newComm():
    global community_name, community_description,community_start_day,community_end_day, comm_loaded

    dialog = ctk.CTkToplevel()
    dialog.title("Create Community")
    w, h = 400, 420  # ← taller to fit date fields
    x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.grab_set()

    result = {"name": None, "description": None, "start_date": None, "end_date": None}

    def confirm():
        name = name_entry_dialog.get().strip()
        desc = desc_entry_dialog.get("1.0", "end").strip()
        start = start_date_entry_dialog.get().strip()
        end = end_date_entry_dialog.get().strip()

        if not name:
            error_label.configure(text="Community name is required.")
            return
        if not start:
            error_label.configure(text="Start date is required.")
            return
        if not end:
            error_label.configure(text="End date is required.")
            return
        if datetime.strptime(end, "%Y-%m-%d") <= datetime.strptime(start, "%Y-%m-%d"):
            error_label.configure(text="End date must be after start date.")
            return

        result["name"] = name
        result["description"] = desc
        result["start_date"] = start
        result["end_date"] = end
        dialog.destroy()

    def cancel():
        dialog.destroy()

    # ── Name ──────────────────────────────────────────────────────────────────
    ctk.CTkLabel(dialog, text="Community Name").pack(anchor="w", padx=20)
    name_entry_dialog = ctk.CTkEntry(dialog)
    name_entry_dialog.pack(padx=20, pady=(0, 10), fill="x")
    name_entry_dialog.focus()

    # ── Description ───────────────────────────────────────────────────────────
    ctk.CTkLabel(dialog, text="Description").pack(anchor="w", padx=20)
    desc_entry_dialog = ctk.CTkTextbox(dialog, height=80)
    desc_entry_dialog.pack(padx=20, pady=(0, 10), fill="both")

    # ── Date fields ───────────────────────────────────────────────────────────
    date_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    date_frame.pack(padx=20, pady=(0, 10), fill="x")
    date_frame.grid_columnconfigure(0, weight=1)
    date_frame.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(date_frame, text="Start Date").grid(row=0, column=0, padx=(0, 5), sticky="w")
    ctk.CTkLabel(date_frame, text="End Date").grid(row=0, column=1, padx=(5, 0), sticky="w")

    start_date_entry_dialog = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", state="readonly")
    start_date_entry_dialog.grid(row=1, column=0, padx=(0, 5), sticky="ew")
    start_date_entry_dialog.bind("<Button-1>", lambda e: open_calendar_popup(start_date_entry_dialog))

    end_date_entry_dialog = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", state="readonly")
    end_date_entry_dialog.grid(row=1, column=1, padx=(5, 0), sticky="ew")
    end_date_entry_dialog.bind("<Button-1>", lambda e: open_calendar_popup(end_date_entry_dialog))

    # ── Error label ───────────────────────────────────────────────────────────
    error_label = ctk.CTkLabel(dialog, text="", text_color="red")
    error_label.pack()

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_frame = ctk.CTkFrame(dialog)
    btn_frame.pack(pady=10)
    ctk.CTkButton(btn_frame, text="Create", command=confirm, width=80).pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="Cancel", command=cancel, width=80).pack(side="left", padx=5)

    dialog.wait_window()

    new_name = result["name"]
    new_desc = result["description"]
    new_start = result["start_date"]
    new_end = result["end_date"]

    if not new_name:  # user cancelled
        return

    clearAll()
    comm_data_panel.pack(pady=8, padx=8)
    save_comm_btn.grid(row=5, column=0, pady=5)
    run_sim_btn.grid(row=5, column=1, pady=5)
    community_name = new_name    
    community_description = new_desc
    community_start_day=new_start
    community_end_day=new_end

    com_desc_entry.configure(text=community_description)
    com_id_entry.configure(text=community_name)
    # Start date update
    start_date_entry.configure(state="normal")
    start_date_entry.delete(0, "end")
    start_date_entry.insert(0, community_start_day)
    start_date_entry.configure(state="readonly")

    # End date update
    end_date_entry.configure(state="normal")
    end_date_entry.delete(0, "end")
    end_date_entry.insert(0, community_end_day)
    end_date_entry.configure(state="readonly")   
    comm_loaded = True

def loadComm():
    global community_name,community_description,comm_loaded,comm_file_path,community_start_day,community_end_day
    #OPEN JSON
    file = filedialog.askopenfile(mode='r', initialdir=COMM_DIR, filetypes=[("JSON files", "*.json")])
    #BACK TO DICT
    if file:
        data = json.load(file)
        file.close()
    else:
        return
    #UPDATE VIEW
    clearAll()
    community_name=format_key(data["name"])
    community_description=data["desc"]
    community_start_day=data["start_date"]
    community_end_day=data["end_date"]
    comm_file_path=file.name

    marker_data=data["systems"]
    

    com_id_entry.configure(text=data["name"])
    com_desc_entry.configure(text=data["desc"])

    # Start date update
    start_date_entry.configure(state="normal")
    start_date_entry.delete(0, "end")
    start_date_entry.insert(0, community_start_day)
    start_date_entry.configure(state="readonly")

    # End date update
    end_date_entry.configure(state="normal")
    end_date_entry.delete(0, "end")
    end_date_entry.insert(0, community_end_day)
    end_date_entry.configure(state="readonly")  

    central_coords=[0.0,0.0]

    for marker in marker_data:
        new_marker=map_widget.set_marker(float(marker["props"]["latitude"]), float(marker["props"]["longitude"]), text=marker["name"], command=on_marker_click)
        new_marker.props=marker["props"]
        new_marker.perm_events=marker["events"]["permanent"]
        new_marker.temp_events=marker["events"]["temporary"]
        all_markers.append(new_marker)
        central_coords[0]+=float(marker["props"]["latitude"])/len(marker_data)
        central_coords[1]+=float(marker["props"]["longitude"])/len(marker_data)

    system_panel.place_forget()
    comm_data_panel.pack(pady=8,padx=8)
    save_comm_btn.grid(row=5, column=0, pady=5)
    run_sim_btn.grid(row=5, column=1,  pady=5)
    map_widget.set_position(central_coords[0], central_coords[1],zoom=14)
    comm_loaded=True

def saveComm():
    global comm_file_path,comm_loaded
    if comm_loaded:
        if comm_file_path:
            filename=comm_file_path
        else:
            filename = filedialog.asksaveasfile(
                                                mode='w',
                                                initialdir=COMM_DIR,
                                                defaultextension=".json",
                                                filetypes=[("JSON files", "*.json")]
                                            ).name
        try:
            with open(filename, 'w') as f:
                json.dump(stateToDict(), f, indent=4)
            comm_file_path=filename
            #print(f"Successfully saved data to {filename}")
            messagebox.showinfo("Great Success",f"Successfully saved data to {filename}")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        messagebox.showerror("Error", "No community loaded. Load a community or create a new one then try again.")
    
    # CHECK FOR ALL DATES TO BE INSIDE SIMULATION DATE

def clearAll():

    global all_markers, selected_marker, ignore_click, system_counter, properties_widgets,comm_file_path,comm_loaded,community_name
    comm_loaded=False
    comm_file_path=""
    community_name=""
    system_counter = 0
    all_markers = []
    selected_marker = None
    ignore_click = False

# -------------------  System Tools

def place_marker(coords):
    global ignore_click, system_counter,comm_loaded,all_markers

    # CHECK IF THERE's A COMMUNITY SELECTED AND IF WE ARE CLICKING ANOTHER MARKER
    if ignore_click or (not comm_loaded):
        ignore_click = False
        return
    
    # PLACES NEW MARKER, HIGHLIGHTS IT
    sys_props ={}
    sys_perm_events={}

    #SYSTEM PROPERTIES DICT CONSTRUCTION
    for prop,data in SYSTEM_PROPERTIES_DATA.items():
        sys_props[prop]=data['default']

    #SYSTEM PERM EVENTS DICT CONSTRUCTION
    for event,data in PERMANENT_EVENTS_DATA.items():
        sys_perm_events[event]={}
        sys_perm_events[event]["enabled"]= data["enabled"]
        sys_perm_events[event]["params"]={}
        sys_perm_events[event]["params"]= {name:prop["default"] for name,prop in data["params"].items()}

    sys_props["latitude"], sys_props["longitude"] = coords[0], coords[1]
    new_marker = map_widget.set_marker(sys_props["latitude"], sys_props["longitude"], text=f"System #{system_counter}", command=on_marker_click)
    new_marker.props=sys_props
    new_marker.perm_events=sys_perm_events
    new_marker.temp_events=None
    all_markers.append(new_marker)
    system_counter += 1
    select_marker(new_marker)

def select_marker(marker):
    global selected_marker
    # CHECK IF CLICKED MARKER IS DIFFERENT FROM ACTUAL SELECTED
    if selected_marker and selected_marker != marker:
        switchColors(selected_marker, marker_color_circle="#9B261E", marker_color_outside="#C5542D")
    selected_marker = marker
    switchColors(selected_marker)
    update_sidebar_fields(selected_marker)

    # SHOW SYSTEM PANEL
    system_panel.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    #tabview.set("System Properties")
    system_panel.lift()

def on_marker_click(marker):
    global ignore_click
    ignore_click = True
    select_marker(marker)

def update_sidebar_fields(marker):

    sys_id_label.configure(text=f"{marker.text}")

    #UPDATE PARAMS FIELDS
    for key, value in marker.props.items():    
        widget=properties_widgets[key]  
        if isinstance(widget, ctk.CTkComboBox):
            widget.set(str(value))
        elif isinstance(widget, ctk.CTkEntry):
            widget.delete(0, "end")
            widget.insert(0,str(value))


    #UPDATE EVENTS
    # ----------- PERMANENT
    for event, values in marker.perm_events.items(): 
        perm_events_widgets[event]["enabled"].set(values["enabled"])
        for param,value in values["params"].items():
        # Handle multiple value parameters
            if type(value) is list:
                for idx,val in enumerate(value):
                    perm_events_widgets[event]["params"][param][idx].delete(0, "end")
                    perm_events_widgets[event]["params"][param][idx].insert(0,str(val))
            else:
                perm_events_widgets[event]["params"][param].delete(0, "end")
                perm_events_widgets[event]["params"][param].insert(0,str(value))


    # Clear existing rows first
    for row in event_tree.get_children():
        event_tree.delete(row)

    # Insert from dict — expected format: {"Event Name": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}} and check if anyevents
    if marker.temp_events :
        for event_name,data in marker.temp_events.items():
            event_tree.insert("", "end", values=(format_key(event_name.rsplit("_", 1)[0]), data["start"], data["end"],data["params"]))


        
def update_markers(*args):
    global selected_marker
    if selected_marker:
   
    # UPDATE PARAMS 
        for key, widget in properties_widgets.items():
            selected_marker.props[key]=SYSTEM_PROPERTIES_DATA[key]["type"](widget.get())
   
    # UPDATE EVENTS
    # ----------- PERMANENT
    for event, values in perm_events_widgets.items():    
        selected_marker.perm_events[event]["enabled"]=bool(values["enabled"].get())
        for param,value in values["params"].items():
            if type(value) is list:
                for idx,val in enumerate(value):
                    selected_marker.perm_events[event]["params"][param][idx]=PERMANENT_EVENTS_DATA[event]["params"][param]["type"][idx](val.get())

            else:
                selected_marker.perm_events[event]["params"][param]=PERMANENT_EVENTS_DATA[event]["params"][param]["type"](value.get())


    # ----------- TEMPORARY
    if not event_tree.get_children():
        selected_marker.temp_events=None
    else:
        selected_marker.temp_events={}
        for row in event_tree.get_children():
            event, start, end, params = event_tree.item(row, "values")
            params=ast.literal_eval(params)
            params={key:TEMPORARY_EVENTS_DATA[unformat_key(event)]["params"][key]["type"](params[key]) for key in list(params.keys())}
            key=unformat_key(event)+"_"+str(secrets.token_hex(2)[:3])
            selected_marker.temp_events[key]={"start":start, 
                                                "end": end,
                                                "params":params}

def delete_selected_marker():
    global selected_marker
    if selected_marker:
        all_markers.remove(selected_marker)
        selected_marker.delete()
        selected_marker = None
        sys_id_label.configure(text="--")
        for item in event_tree.get_children():
            event_tree.delete(item)
        for widget in properties_widgets.values():
            if isinstance(widget, ctk.CTkComboBox):
                widget.set("")
            else:
                widget.delete(0, tkinter.END)
        system_panel.place_forget()

def close_sys_panel():
    global selected_marker
    switchColors(selected_marker, marker_color_circle="#9B261E", marker_color_outside="#C5542D")
    selected_marker = None
    system_panel.place_forget()

def new_event():
    dialog = ctk.CTkToplevel()
    dialog.title("New Event")
    w, h = 400, 320
    x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.grab_set()

    result = {"event": None, "start": None, "end": None,"params":None}

    def confirm():
        event = event_entry.get().strip()
        start = start_entry.get().strip()
        end = end_entry.get().strip()
        params = {prop:parameter_widgets[prop].get().strip() for prop in list(parameter_widgets.keys())}

        if not event:
            error_label.configure(text="Event name is required.")
            return
        if not start:
            error_label.configure(text="Start date is required.")
            return
        if not end:
            error_label.configure(text="End date is required.")
            return
        if datetime.strptime(end, "%Y-%m-%d") <= datetime.strptime(start, "%Y-%m-%d"):
            error_label.configure(text="End date must be after start date.")
            return

        result["event"] = event
        result["start"] = start
        result["end"] = end
        result["params"] = params
        dialog.destroy()

    def cancel():
        dialog.destroy()

    def setupParameter(event):
        event=unformat_key(event)
        for widget in parameter_frame.winfo_children():
            widget.destroy()
        parameter_widgets.clear()
        for key,value in TEMPORARY_EVENTS_DATA[event]["params"].items():
            ctk.CTkLabel(parameter_frame, text=format_key(key)).pack(anchor="w", padx=20, pady=(15, 2))
            entry=ctk.CTkEntry(parameter_frame, width=140,height=20)
            entry.insert(0, value["default"])
            entry.pack()
            parameter_widgets[key]=entry



    # ── Event name ────────────────────────────────────────────────────────────
    ctk.CTkLabel(dialog, text="Event Name").pack(anchor="w", padx=20, pady=(15, 2))
    event_entry = ctk.CTkComboBox(dialog,values=[format_key(ev) for ev in TEMPORARY_EVENTS_DATA.keys()],command=setupParameter)
    event_entry.pack(padx=20, fill="x")
    event_entry.focus()

    # ── Event Parameters ────────────────────────────────────────────────────────────

    parameter_widgets={}
    parameter_frame=ctk.CTkFrame(dialog, fg_color="transparent")
    parameter_frame.pack()
    setupParameter(list(TEMPORARY_EVENTS_DATA.keys())[0])

    # ── Date fields ───────────────────────────────────────────────────────────
    date_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    date_frame.pack(padx=20, pady=(15, 0), fill="x")
    date_frame.grid_columnconfigure(0, weight=1)
    date_frame.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(date_frame, text="Start Date").grid(row=0, column=0, sticky="w", padx=(0, 5))
    ctk.CTkLabel(date_frame, text="End Date").grid(row=0, column=1, sticky="w", padx=(5, 0))

    start_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", state="readonly")
    start_entry.grid(row=1, column=0, sticky="ew", padx=(0, 5))
    start_entry.bind("<Button-1>", lambda e: open_calendar_popup(start_entry))

    end_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", state="readonly")
    end_entry.grid(row=1, column=1, sticky="ew", padx=(5, 0))
    end_entry.bind("<Button-1>", lambda e: open_calendar_popup(end_entry))

    # ── Error & buttons ───────────────────────────────────────────────────────
    error_label = ctk.CTkLabel(dialog, text="", text_color="red")
    error_label.pack(pady=(10, 0))

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=10)
    ctk.CTkButton(btn_frame, text="Add", command=confirm, width=80,
                  fg_color="#2980b9", hover_color="#3498db").pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="Cancel", command=cancel, width=80,
                  fg_color="#922b21", hover_color="#c0392b").pack(side="left", padx=5)

    dialog.wait_window()

    if result["event"]:
        event_tree.insert("", "end", values=(result["event"], result["start"], result["end"],result["params"]))
    
    update_markers()


def delete_event():
    selected = event_tree.selection()
    if selected:
        event_tree.delete(*selected)
    update_markers()

# --- UI Setup ---
root = ctk.CTk()
root.title("PV Community Planner")


# ── Community Panel  ───────────────────────────────────────────────────────────
comm_panel = ctk.CTkFrame(root, corner_radius=12, border_width=2, border_color="#444")

comm_data_panel = ctk.CTkFrame(comm_panel)


comm_button_panel = ctk.CTkFrame(comm_panel)
comm_button_panel.pack(pady=8,padx=8)

# ── Community Name label (spans both columns) ──────────────────────────────────
"""
ctk.CTkLabel(
    comm_data_panel,
    text="Community Name",
    font=("Arial", 10),
    text_color="#aab4c8",
).grid(row=0, column=0, columnspan=2, pady=0)
"""
com_id_entry = ctk.CTkLabel(
    comm_data_panel,
    text="-",
    font=("Arial", 15, "bold"),
    text_color="#ffffff",
)
com_id_entry.grid(row=1, column=0, columnspan=2, pady=4)

com_desc_entry = ctk.CTkLabel(
    comm_data_panel,
    text="",
    font=("Arial", 11),
    text_color="#aab4c8",
    width=260,        # ← fixed width in pixels
    wraplength=250,   # ← optional: wraps long text within the fixed width
    justify="left"   # ← left-aligns wrapped/multiline text
)
com_desc_entry.grid(row=2, column=0, columnspan=2, pady=(0, 10))

# ── Date picker labels ─────────────────────────────────────────────────────────
ctk.CTkLabel(
    comm_data_panel,
    text="Simulation Start Date",
    font=("Arial", 10),
    text_color="#aab4c8",
).grid(row=3, column=0, padx=(10, 5), pady=(4, 2), sticky="w")

ctk.CTkLabel(
    comm_data_panel,
    text="Simulation End Date",
    font=("Arial", 10),
    text_color="#aab4c8",
).grid(row=3, column=1, padx=(5, 10), pady=(4, 2), sticky="w")

# ── Date picker entries ────────────────────────────────────────────────────────
start_date_entry = ctk.CTkEntry(
    comm_data_panel,
    placeholder_text="YYYY-MM-DD",
    font=("Arial", 12),
    state="readonly",
    width=130,
)
start_date_entry.grid(row=4, column=0, padx=(10, 5), pady=(0, 10), sticky="ew")

start_date_entry.bind("<Button-1>", lambda e: globals().update(community_start_day=open_calendar_popup(start_date_entry)))

end_date_entry = ctk.CTkEntry(
    comm_data_panel,
    placeholder_text="YYYY-MM-DD",
    font=("Arial", 12),
    state="readonly",
    width=130,
)
end_date_entry.grid(row=4, column=1, padx=(5, 10), pady=(0, 10), sticky="ew")
end_date_entry.bind("<Button-1>", lambda e: globals().update(community_end_day=open_calendar_popup(end_date_entry)))

# ── Make columns share space equally ──────────────────────────────────────────
comm_data_panel.grid_columnconfigure(0, weight=1)
comm_data_panel.grid_columnconfigure(1, weight=1)

save_comm_btn=ctk.CTkButton(comm_data_panel, text="💾  Save Community", command=saveComm,
              fg_color="#c0392b", hover_color="#e74c3c")

run_sim_btn=ctk.CTkButton(comm_data_panel, text="▶  Run Simulation", command=runSim,
              fg_color="#27ae60", hover_color="#2ecc71")

save_comm_btn.grid(row=5, column=0,  pady=5);save_comm_btn.grid_forget()
run_sim_btn.grid(row=5, column=1,  pady=5);run_sim_btn.grid_forget()

new_comm_btn=ctk.CTkButton(comm_button_panel, text="＋  New Community", command=newComm,
              fg_color="#27ae60", hover_color="#2ecc71", width=240)
load_comm_btn=ctk.CTkButton(comm_button_panel, text="⬆  Load Community", command=loadComm,
              fg_color="#2980b9", hover_color="#3498db", width=240)

new_comm_btn.pack(fill="x", pady=5);load_comm_btn.pack(fill="x", pady=5);
#ctk.CTkButton(comm_button_panel, text="🐛  DEBUG", command=debug_print,fg_color="#222", hover_color="#444", width=240).pack(fill="x", pady=5, padx=10)

# ── PV parameter Panel ──────────────────────────────────────────────────────

system_panel = ctk.CTkFrame(root, corner_radius=12,width=350)

sys_id_label = ctk.CTkLabel(system_panel, text="-", font=("Arial", 15, "bold"), text_color="#ffffff")
sys_id_label.pack(pady=(5, 5))


tabview = ctk.CTkTabview(system_panel)
tabview.pack(fill="both", expand=True, padx=10, pady=10)

# Add tabs
tabview.add("System Properties")
tabview.add("Permanent Events")
tabview.add("Temporary Events")


# SYSTEM PROPERTIES TAB CONTENT
for idx, key in enumerate(SYSTEM_PROPERTIES_DATA.keys()):
    row = idx // 2
    col = idx % 2

    lbl_text = key.replace("_", " ").title()
    ctk.CTkLabel(tabview.tab("System Properties"), text=lbl_text, font=("Arial", 9), text_color="#ecf0f1",
                 anchor="w",height=20).grid(row=row*2, column=col, sticky="w", padx=(8, 4), pady=(8, 0))

    if key in ["module_cec", "inverter_cec"]:
        ent = ctk.CTkComboBox(
            tabview.tab("System Properties"),
            values=CEC_MODULES if key == "module_cec" else CEC_INVERTERS,
            width=140,
            height=20,
            command=update_markers,
        )
        ent.set(str(SYSTEM_PROPERTIES_DATA[key]))
    else:
        ent = ctk.CTkEntry(tabview.tab("System Properties"), width=140, placeholder_text=str(SYSTEM_PROPERTIES_DATA[key]),height=20)
        ent.bind("<KeyRelease>", update_markers)

    ent.grid(row=row*2+1, column=col, padx=(8, 4), pady=(2, 0))
    properties_widgets[key] = ent


# PERMANENT EVENTS TAB CONTENT

for event, parameters in PERMANENT_EVENTS_DATA.items():
    # ── LabelFrame per event ──────────────────────────────────────────────────
    event_frame = tkinter.LabelFrame(
        tabview.tab("Permanent Events"),
        text=format_key(event),
        fg="#aab4c8",
        bg="#2b2b2b",
        font=("Arial", 11, "bold"),
        bd=1,
        relief="flat"
    )
    event_frame.pack(fill="x", padx=10, pady=6)

    perm_events_widgets[event] = {"enabled": None, "params": {}}

    # ── Enabled checkbox ──────────────────────────────────────────────────────
    enabled_var = ctk.BooleanVar(value=parameters["enabled"])
    ctk.CTkCheckBox(event_frame, text="Enabled", variable=enabled_var,checkbox_height=15,checkbox_width=15,border_width=1,corner_radius=5,command=update_markers).pack(anchor="w", padx=10, pady=(6, 4))
    perm_events_widgets[event]["enabled"] = enabled_var

    # ── Parameter entries ─────────────────────────────────────────────────────
    for key,value in parameters["params"].items():
        row = ctk.CTkFrame(event_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(row, text=format_key(key), width=120, anchor="w",height=20).pack(side="left")

        # Handle multiple value parameters
        if type(value["default"]) is list:
            param_entry = [ctk.CTkEntry(row, width=70,height=20) for _ in value["default"]]
            for idx,entry in enumerate(param_entry):
                entry.configure(state="normal")
                entry.bind("<KeyRelease>", update_markers)
                entry.insert(0, str(value["default"][idx]))
                entry.pack(side="left", padx=(5, 0))
        else:
            param_entry = ctk.CTkEntry(row, width=150,height=20)
            param_entry.configure(state="normal")
            param_entry.bind("<KeyRelease>", update_markers)
            param_entry.insert(0, str(value["default"]))
            param_entry.pack(side="left", padx=(5, 0))

        perm_events_widgets[event]["params"][key] = param_entry
    

# TEMPORARY EVENTS TAB CONTENT

# Treeview inside timeline
# Style treeview to match dark panel
style = ttk.Style()
style.theme_use("clam")

style.configure("Treeview",
                background="#2b2b2b",
                foreground="white",
                fieldbackground="#2b2b2b",
                borderwidth=0,
                rowheight=28,
                font=("Arial", 10))

style.configure("Treeview.Heading",
                background="#1a1a1a",
                foreground="#aaaaaa",
                borderwidth=0,
                font=("Arial", 10))

style.map("Treeview",
          background=[("selected", "#2980b9")],
          foreground=[("selected", "white")])

style.map("Treeview.Heading",
          background=[("active", "#222222")])

# Treeview inside timeline

cols = ("Event", "Start", "End","Parameters")
event_tree = ttk.Treeview(tabview.tab("Temporary Events"), columns=cols, show="headings", height=7)
for col in cols:
    event_tree.heading(col, text=col)
event_tree.column("Event", width=60)
event_tree.column("Start", width=60)
event_tree.column("End", width=60)
event_tree.column("Parameters", width=140)
event_tree.pack(fill="both", expand=True)
#event_tree.bind("<<TreeviewSelect>>", on_tree_select)

ctk.CTkButton(tabview.tab("Temporary Events"), text="New Event", command=new_event,
              fg_color="#2980b9", hover_color="#3498db").pack(side="left", fill="x", expand=True, pady=5,padx=10)
ctk.CTkButton(tabview.tab("Temporary Events"), text="Delete Event", command=delete_event,
              fg_color="#922b21", hover_color="#c0392b").pack(side="left", fill="x", expand=True, pady=5,padx=10)


#PANEL BUTTONS
ctk.CTkButton(system_panel, text="🗑️ Remove System", command=delete_selected_marker,
              fg_color="#c0392b", hover_color="#e74c3c").pack(fill="x", pady=5,padx=10)
ctk.CTkButton(system_panel, text="Close", command=close_sys_panel,
              fg_color="#3498db", hover_color="#297ab1").pack(fill="x", pady=5,padx=10)

# PLACE PANELS
comm_panel.place(relx=0.0, rely=0.0, anchor="nw", x=10, y=10)
system_panel.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
system_panel.place_forget()


# ── Map ───────────────────────────────────────────────
map_widget = tkintermapview.TkinterMapView(root, width=850, height=600)
map_widget.pack(side="top", fill="both", expand=True)
map_widget.set_position(47.028, 8.298)
map_widget.set_zoom(13)
map_widget.add_left_click_map_command(place_marker)

# LIFT PANELS
comm_panel.lift()

root.mainloop()
