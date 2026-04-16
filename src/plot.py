# plotting functions for fault injection simulation results

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# color assigned to each fault type, used across all plots for consistency
FAULT_COLORS = {
    "soiling":        "orange",
    "degradation":    "blue",
    "pid":            "red",
    "open_string":    "purple",
    "inverter_fault": "green",
}


def save_fig(fig, save_path, filename):
    # saves the figure as a PNG if a save_path directory is provided
    if save_path is not None:
        os.makedirs(save_path, exist_ok=True)
        fig.savefig(os.path.join(save_path, filename), bbox_inches="tight", dpi=150)


def fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries):
    # draws a colored background span for each active fault window on the given axis
    # also appends it to legend_entries so it can be included in the legend
    for f in fault_list:
        ftype = f["type"]
        fstart = pd.Timestamp(f.get("start", sim_start), tz=tz)
        fend = pd.Timestamp(f.get("end", sim_end), tz=tz)
        color = FAULT_COLORS.get(ftype, "gray")
        ax.axvspan(fstart, fend, alpha=0.12, color=color)

        # label includes date range only when the fault does not span the full window
        if "start" not in f and "end" not in f:
            label = ftype
        else:
            label = f"{ftype} ({fstart.strftime('%b %d')} to {fend.strftime('%b %d')})"

        legend_entries.append(mpatches.Patch(color=color, alpha=0.5, label=label))


def plot_power_comparison(sim_healthy, sim_faulty, story, systems, save_path=None):
    # time series plot showing healthy and faulty AC power side by side for each system
    # fault windows are shaded so you can see exactly when each fault was active
    # power is shown in kW

    sim_start = story["timeframe"]["start"]
    sim_end = story["timeframe"]["end"]
    tz = list(systems.values())[0]["timezone"]

    num_systems = len(systems)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, systems):
        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        ax.plot(healthy_power.index, healthy_power / 1000, color="black", linewidth=0.7)
        ax.plot(faulty_power.index, faulty_power / 1000, color="steelblue", linewidth=0.7)

        legend_entries = [
            Line2D([0], [0], color="black",     linewidth=1.5, label="healthy"),
            Line2D([0], [0], color="steelblue", linewidth=1.5, label="faulty"),
        ]

        fault_list = story["faults"].get(sys_id, [])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(sys_id)
        ax.set_ylabel("AC Power (kW)")
        ax.set_xlabel("Time")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle(f"Healthy vs faulty power  |  {sim_start} to {sim_end}", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "power_comparison.png")
    plt.show()


def plot_power_ratio(sim_healthy, sim_faulty, story, systems, save_path=None):
    # daily energy ratio (faulty / healthy) per system, shown as a line over the simulation window
    # a value of 1.0 means no loss, 0.7 means the fault reduced energy by 30%

    sim_start = story["timeframe"]["start"]
    sim_end = story["timeframe"]["end"]
    tz = list(systems.values())[0]["timezone"]

    num_systems = len(systems)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, systems):
        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        daily_healthy_kwh = (healthy_power / 1000).resample("D").sum()
        daily_faulty_kwh = (faulty_power / 1000).resample("D").sum()

        # ratio of faulty to healthy daily yield, masked on days where healthy is effectively zero
        daily_ratio = (daily_faulty_kwh / daily_healthy_kwh.replace(0, float("nan"))).clip(0, 1.1)

        ax.plot(daily_ratio.index, daily_ratio, color="steelblue", linewidth=1.2, marker="o", markersize=2.5)
        ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
        ax.set_ylim(0, 1.15)

        legend_entries = [
            Line2D([0], [0], color="black",     linewidth=1.2, linestyle="--", label="no fault (ratio = 1)"),
            Line2D([0], [0], color="steelblue", linewidth=1.5, label="faulty / healthy (daily)"),
        ]

        fault_list = story["faults"].get(sys_id, [])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(sys_id)
        ax.set_ylabel("Daily energy ratio (faulty / healthy)")
        ax.set_xlabel("Date")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle(f"Daily energy ratio  |  {sim_start} to {sim_end}", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "power_ratio.png")
    plt.show()


def plot_daily_energy_loss(sim_healthy, sim_faulty, story, systems, save_path=None):
    # stacked bar chart showing daily energy loss (kWh) broken down by active fault, per system
    # each bar's total height is the actual measured loss (healthy minus faulty)

    sim_start = story["timeframe"]["start"]
    sim_end = story["timeframe"]["end"]
    tz = list(systems.values())[0]["timezone"]

    num_systems = len(systems)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, systems):
        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        daily_healthy_kwh = (healthy_power / 1000).resample("D").sum()
        daily_faulty_kwh = (faulty_power / 1000).resample("D").sum()
        daily_loss_kwh = (daily_healthy_kwh - daily_faulty_kwh).clip(lower=0)

        fault_list = story["faults"].get(sys_id, [])
        # keep insertion order while deduplicating fault types
        seen = set()
        fault_types_present = [f["type"] for f in fault_list if not (f["type"] in seen or seen.add(f["type"]))]

        # for each fault type, compute its share of the daily loss
        per_fault_loss = {ftype: pd.Series(0.0, index=daily_loss_kwh.index) for ftype in fault_types_present}

        for day in daily_loss_kwh.index:
            active_today = []
            for f in fault_list:
                fstart = pd.Timestamp(f.get("start", sim_start), tz=tz)
                fend = pd.Timestamp(f.get("end", sim_end), tz=tz)
                if fstart <= day <= fend:
                    active_today.append(f["type"])
            if active_today:
                share = daily_loss_kwh[day] / len(active_today)
                for ftype in active_today:
                    per_fault_loss[ftype][day] = share

        bottom = pd.Series(0.0, index=daily_loss_kwh.index)
        legend_entries = []
        for ftype in fault_types_present:
            color = FAULT_COLORS.get(ftype, "gray")
            ax.bar(
                per_fault_loss[ftype].index,
                per_fault_loss[ftype].values,
                bottom=bottom.values,
                color=color,
                width=0.8,
                alpha=0.8,
            )
            legend_entries.append(mpatches.Patch(color=color, alpha=0.8, label=ftype))
            bottom = bottom + per_fault_loss[ftype]

        ax.set_title(sys_id)
        ax.set_ylabel("Daily energy loss (kWh)")
        ax.set_xlabel("Date")
        if legend_entries:
            ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle(f"Daily energy loss from faults  |  {sim_start} to {sim_end}", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "daily_energy_loss.png")
    plt.show()


def plot_daily_energy_comparison(sim_healthy, sim_faulty, story, systems, save_path=None):
    # grouped bar chart comparing daily energy (kWh) between healthy and faulty, per system
    # each day has two bars side by side: one for healthy, one for faulty
    # this gives a cleaner view than the hourly timeseries when looking at the full simulation window
    # fault windows are shaded in the background so we can see which bars are affected

    sim_start = story["timeframe"]["start"]
    sim_end = story["timeframe"]["end"]
    tz = list(systems.values())[0]["timezone"]

    num_systems = len(systems)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, systems):
        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        daily_healthy_kwh = (healthy_power / 1000).resample("D").sum()
        daily_faulty_kwh = (faulty_power / 1000).resample("D").sum()

        # offset each bar by half a day so healthy and faulty sit side by side
        bar_width = pd.Timedelta(hours=9)
        half_width = pd.Timedelta(hours=4, minutes=30)

        ax.bar(daily_healthy_kwh.index - half_width, daily_healthy_kwh.values,
               width=bar_width, color="black", alpha=0.7, label="healthy")
        ax.bar(daily_faulty_kwh.index + half_width, daily_faulty_kwh.values,
               width=bar_width, color="steelblue", alpha=0.7, label="faulty")

        legend_entries = [
            mpatches.Patch(color="black",     alpha=0.7, label="healthy"),
            mpatches.Patch(color="steelblue", alpha=0.7, label="faulty"),
        ]

        fault_list = story["faults"].get(sys_id, [])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(sys_id)
        ax.set_ylabel("Daily energy (kWh)")
        ax.set_xlabel("Date")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle(f"Daily energy: healthy vs faulty  |  {sim_start} to {sim_end}", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "daily_energy_comparison.png")
    plt.show()
