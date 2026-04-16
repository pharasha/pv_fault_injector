import tkinter
from tkinter import ttk,filedialog,messagebox
import tkintermapview
import pvlib
import json
from tkcalendar import DateEntry

# --- Configuration & Templates ---
PV_DEFAULT = {
    "latitude":47.0108,
    "longitude":8.3204,
    "module_cec": "Canadian_Solar_Inc__CS6X_305P",
    "inverter_cec": "Fronius_USA__Fronius_Primo_3_8_1_208_240__208V_",
    "altitude_m": 470,
    "tilt_deg": 20,
    "azimuth_deg": 180,
    "modules_per_string": 4,
    "strings": 2,
}


COMM_DIR="./data"

EVENTS={"temporary":["open_string","inverter_fault"],"permanent":["soiling","snow","degradation"]}

CEC_MODULES=list(pvlib.pvsystem.retrieve_sam('cecmod').columns)
CEC_INVERTERS=list(pvlib.pvsystem.retrieve_sam('CECInverter').columns) 

all_markers = []
selected_marker = None
ignore_click = False 
system_counter = 0
entries = {} 

# --- Logic Functions ---

def clearAll():
    all_markers = []
    selected_marker = None
    ignore_click = False 
    system_counter = 0
    entries = {} 


def loadComm():
    file = filedialog.askopenfile(mode='r',initialdir=COMM_DIR)

def saveComm():
    if com_id_label.get():
        full_dict={}
        filename= COMM_DIR+"/"+f"{com_id_label.get()}"+".json"
        for marker in all_markers:
            full_dict[marker.system_id]={"parameters":marker.pv_data,"events":{"perm_events":marker.global_status,"temp_events":marker.timeline}}
        try:
            with open(filename, 'w') as f:
                json.dump(full_dict, f, indent=4)
            print(f"Successfully saved data to {filename}")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        messagebox.showerror("Error", "Community name cannot be empty. Enter a community name and try again.")

def runSim():
    None

def debug_print():
    print(all_markers,entries)

def update_timeline_display(marker):
    """Refreshes the Treeview with events for the selected pin."""
    # Clear current list
    for item in event_tree.get_children():
        event_tree.delete(item)
    
    # Repopulate from marker data
    for idx, event in enumerate(marker.timeline):
        event_tree.insert("", "end", iid=idx, values=(event['desc'],event['start'], event['end']))

def on_tree_select(event):
    """Loads selected timeline event into the entry boxes for editing."""
    selected_items = event_tree.selection()
    if selected_items:
        item_id = selected_items[0]
        values = event_tree.item(item_id, "values")
        event_entry.delete(0, tkinter.END)
        event_entry.insert(0, values[0])
        start_time_entry.delete(0, tkinter.END)
        start_time_entry.insert(0, values[1])
        end_time_entry.delete(0, tkinter.END)
        end_time_entry.insert(0, values[2])

def add_event():
    """Adds a new timeline event."""
    if selected_marker:
        event_data = {
            "desc": event_entry.get(),
            "start": start_time_entry.get(),
            "end": end_time_entry.get()
        }
        selected_marker.timeline.append(event_data)
        update_timeline_display(selected_marker)

def update_selected_event():
    """Saves changes back to the specific event selected in the Treeview."""
    selected_items = event_tree.selection()
    if selected_marker and selected_items:
        idx = int(selected_items[0])
        selected_marker.timeline[idx] = {
            "desc": event_entry.get(),
            "start": start_time_entry.get(),
            "end": end_time_entry.get()
        }
        update_timeline_display(selected_marker)

def delete_event():
    """Removes the selected event from the timeline."""
    selected_items = event_tree.selection()
    if selected_marker and selected_items:
        idx = int(selected_items[0])
        del selected_marker.timeline[idx]
        update_timeline_display(selected_marker)

def save_properties(*args):
    """Saves entry data, global checkbox states, and moves marker."""
    global selected_marker
    if selected_marker:
        for key in PV_DEFAULT.keys():
            selected_marker.pv_data[key] = entries[key].get()
        selected_marker.global_status = {EVENTS["permanent"][idx]:check_vars[idx].get() for idx in range(len(check_vars))}
        
        try:
            new_lat = float(entries["latitude"].get())
            new_lon = float(entries["longitude"].get())
            data, sys_id, timeline, status = selected_marker.pv_data, selected_marker.system_id, \
                                            selected_marker.timeline, selected_marker.global_status
            selected_marker.delete()
            new_marker = map_widget.set_marker(new_lat, new_lon, text=sys_id,
                                               marker_color_circle="#2ecc71", marker_color_outside="#27ae60",
                                               command=on_marker_click)
            new_marker.pv_data, new_marker.system_id, new_marker.timeline, new_marker.global_status = data, sys_id, timeline, status
            if selected_marker in all_markers: all_markers.remove(selected_marker)
            all_markers.append(new_marker)
            selected_marker = new_marker
        except ValueError:
            print("Invalid coordinates.")

def update_sidebar_fields(marker):
    sys_id_label.config(text=f"{marker.system_id}")
    for idx,check_var in enumerate(check_vars):
        check_var.set(marker.global_status[EVENTS["permanent"][idx]])
    entries["latitude"].delete(0, tkinter.END); entries["latitude"].insert(0, str(marker.position[0]))
    entries["longitude"].delete(0, tkinter.END); entries["longitude"].insert(0, str(marker.position[1]))
    for key, value in marker.pv_data.items():
        if key in entries:
            entries[key].delete(0, tkinter.END); entries[key].insert(0, str(value))
    update_timeline_display(marker)

def on_marker_click(marker):
    global ignore_click
    ignore_click = True
    highlight_marker(marker)

def switchColors(marker,marker_color_circle="#2ecc71", marker_color_outside="#27ae60"):
    map_widget.canvas.itemconfig(marker.polygon, fill=marker_color_outside,outline=marker_color_outside)
    map_widget.canvas.itemconfig(marker.big_circle, fill=marker_color_circle,outline=marker_color_outside)

def highlight_marker(marker):
    global selected_marker

    if selected_marker and selected_marker != marker:
        switchColors(selected_marker,marker_color_circle="#9B261E",marker_color_outside= "#C5542D")
    selected_marker=marker
    switchColors(selected_marker)
    timeline_frame.pack(side="bottom", fill="x")
    update_sidebar_fields(selected_marker)

def add_marker_event(coords):
    global ignore_click, system_counter
    if ignore_click:
        ignore_click = False
        return
    system_counter += 1
    sys_id = f"System #{system_counter}"
    new_marker = map_widget.set_marker(coords[0], coords[1], text=sys_id, command=on_marker_click)
    pv_def=PV_DEFAULT.copy()
    pv_def["latitude"],pv_def["longitude"]=coords[0], coords[1]
    new_marker.pv_data, new_marker.system_id, new_marker.timeline, new_marker.global_status = pv_def, sys_id, [], {EVENTS["permanent"][idx]:False for idx in range(len(check_vars))}
    all_markers.append(new_marker)
    highlight_marker(new_marker)

def delete_selected_marker():
    global selected_marker
    if selected_marker:
        all_markers.remove(selected_marker)
        selected_marker.delete(); selected_marker = None
        sys_id_label.config(text="--")
        for item in event_tree.get_children(): event_tree.delete(item)
        for entry in entries.values(): entry.delete(0, tkinter.END)
    if all_markers: 
        highlight_marker(all_markers[-1])
    else:
        timeline_frame.pack_forget()





# Style Functions

def disableChildren(parent):
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        if wtype not in ('Frame','Labelframe','TFrame','TLabelframe','TSeparator'):
            child.configure(state='disable')
        else:
            disableChildren(child)

def enableChildren(parent):
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        print (wtype)
        if wtype not in ('Frame','Labelframe','TFrame','TLabelframe','TSeparator'):
            child.configure(state='normal')
        else:
            enableChildren(child)


# --- UI Setup ---
root = tkinter.Tk()
root.geometry("1400x900")
root.title("Solar PV Site Planner - Editable Timeline")


# 1. Simulation Frame (Top)
sim_frame = tkinter.Frame(root, height=50, bg="#34495e", padx=10, pady=10)
#sim_frame.pack(side="top", fill="x")

# 2. Sidebar
sidebar = tkinter.Frame(root, width=300, bg="#2c3e50", padx=15, pady=15)
sidebar.pack(side="right", fill="y")

tkinter.Label(sidebar, text="Community Name", font=("Arial", 10), bg="#2c3e50", fg="#ffffff").pack(pady=(0, 2))
com_id_label = tkinter.Entry(sidebar, bg="#34495e", fg="white", insertbackground="white", bd=0)
com_id_label.pack(pady=(0, 10))

tkinter.Button(sidebar, text="Load Community", command=loadComm, bg="#3498db", fg="white", bd=0).pack(fill="x")
tkinter.Button(sidebar, text="Save Community", command=saveComm, bg="#e74c3c", fg="white", bd=0 ).pack(fill="x")
tkinter.Button(sidebar, text="DEBUG", command=debug_print, bg="#000000", fg="white", bd=0 ).pack(fill="x")

#tkinter.Button(sidebar, text="Run Simulation", command=None, bg="#27ae60", fg="white", bd=0).pack(fill="x",pady=8)


ttk.Separator(sidebar, orient=tkinter.HORIZONTAL).pack(side=tkinter.TOP, fill=tkinter.X, pady=10)

tkinter.Label(sidebar, text="System", font=("Arial", 10), bg="#2c3e50", fg="#f1c40f").pack(pady=(0, 2))
sys_id_label = tkinter.Label(sidebar, text="--", font=("Arial", 14, "bold"), bg="#2c3e50", fg="#f1c40f")
sys_id_label.pack(pady=(0, 10))

for key in PV_DEFAULT.keys():
    lbl_text = key.replace("_", " ").title()
    tkinter.Label(sidebar, text=lbl_text, bg="#2c3e50", fg="#ecf0f1", font=("Arial", 9)).pack(anchor="w", pady=(8, 0))
    if key in ["module_cec","inverter_cec"]:
        ent=tkinter.ttk.Combobox(sidebar,values=CEC_MODULES if key=="module_cec" else CEC_INVERTERS)
        ent.bind("<<ComboboxSelected>>",save_properties)
    else:
        ent = tkinter.Entry(sidebar, bg="#34495e", fg="white", insertbackground="white", bd=0)
        ent.bind("<KeyRelease>",save_properties)
    ent.pack(fill="x", ipady=3); entries[key] = ent

#tkinter.Button(sidebar, text="Save & Move Pin", command=save_properties, bg="#27ae60", fg="white", bd=0, pady=8).pack(fill="x", pady=(20, 10))
tkinter.Button(sidebar, text="Delete Pin", command=delete_selected_marker, bg="#e74c3c", fg="white", bd=0, pady=8).pack(fill="x")

# 3. Timeline (Bottom)
timeline_frame = tkinter.Frame(root, height=450, bg="#34495e", padx=10, pady=10)

# Event List (Treeview)
cols = ("Event","Start", "End")
event_tree = ttk.Treeview(timeline_frame, columns=cols, show="headings", height=8)
for col in cols: event_tree.heading(col, text=col)
event_tree.column("Event", width=400); event_tree.column("Start", width=150); event_tree.column("End", width=150)
event_tree.pack(side="left", fill="both", expand=True, padx=(0, 10))
event_tree.bind("<<TreeviewSelect>>", on_tree_select)

event_controls = tkinter.Frame(timeline_frame, bg="#34495e")
event_controls.pack(side="right")

# Global Checkboxes
check_vars = [tkinter.BooleanVar() for f in EVENTS["permanent"]]
cb_frame = tkinter.Frame(event_controls, bg="#34495e")
cb_frame.pack(fill="x", pady=(0, 5))
tkinter.Label(cb_frame, text="Permanent Events", bg="#34495e", fg="white", font=("Arial", 8)).pack(anchor="w")
for idx,check_var in enumerate(check_vars):
    tkinter.Checkbutton(cb_frame, text=EVENTS["permanent"][idx].capitalize(), variable=check_var, bg="#34495e", fg="black", command=save_properties).pack(side="left")
    


# Event Entry Fields
tkinter.Label(event_controls, text="Event Title", bg="#34495e", fg="white", font=("Arial", 8)).pack(anchor="w")
event_entry = tkinter.ttk.Combobox(event_controls,values=EVENTS["temporary"], width=35); event_entry.pack(pady=(0, 5))
tkinter.Label(event_controls, text="Start Date", bg="#34495e", fg="white", font=("Arial", 8)).pack(anchor="w")
start_time_entry = DateEntry(event_controls, width=35, background='darkblue',
                foreground='white', borderwidth=2)
start_time_entry.pack(pady=(0, 5))
tkinter.Label(event_controls, text="End Date", bg="#34495e", fg="white", font=("Arial", 8)).pack(anchor="w")
end_time_entry = DateEntry(event_controls, width=35, background='darkblue',
                foreground='white', borderwidth=2)
end_time_entry.pack(pady=(0, 5))

# Event Action Buttons
btn_frame = tkinter.Frame(event_controls, bg="#34495e")
btn_frame.pack(fill="x", pady=5)
tkinter.Button(btn_frame, text="Add New", command=add_event, bg="#3498db", fg="white", bd=0, width=10).pack(side="left", padx=2)
tkinter.Button(btn_frame, text="Update", command=update_selected_event, bg="#f39c12", fg="white", bd=0, width=10).pack(side="left", padx=2)
tkinter.Button(btn_frame, text="Delete", command=delete_event, bg="#c0392b", fg="white", bd=0, width=10).pack(side="left", padx=2)

# 3. Map
map_widget = tkintermapview.TkinterMapView(root, width=850, height=600)
map_widget.pack(side="top", fill="both", expand=True)
map_widget.set_position(47.028, 8.298); map_widget.set_zoom(13)
map_widget.add_left_click_map_command(add_marker_event)


root.mainloop()