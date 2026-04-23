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


def plot_power_comparison(sim_healthy, sim_faulty, community, save_path=None):
    # time series plot showing healthy and faulty AC power side by side for each system
    # fault windows are shaded so you can see exactly when each fault was active
    # power is shown in kW

    num_systems = len(community)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, community):
        sim_start = community[sys_id]["timeframe"]["start"]
        sim_end   = community[sys_id]["timeframe"]["end"]
        tz = sim_healthy.timezone[sys_id]

        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        ax.plot(healthy_power.index, healthy_power / 1000, color="black", linewidth=0.7)
        ax.plot(faulty_power.index, faulty_power / 1000, color="steelblue", linewidth=0.7)

        legend_entries = [
            Line2D([0], [0], color="black",     linewidth=1.5, label="healthy"),
            Line2D([0], [0], color="steelblue", linewidth=1.5, label="faulty"),
        ]

        fault_list = sim_faulty.build_fault_list(community[sys_id]["events"])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(f"{sys_id}  |  {sim_start} to {sim_end}")
        ax.set_ylabel("AC Power (kW)")
        ax.set_xlabel("Time")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle("Healthy vs faulty power", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "power_comparison.png")
    plt.show()


def plot_power_ratio(sim_healthy, sim_faulty, community, save_path=None):
    # daily energy ratio (faulty / healthy) per system, shown as a line over the simulation window
    # a value of 1.0 means no loss, 0.7 means the fault reduced energy by 30%

    num_systems = len(community)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, community):
        sim_start = community[sys_id]["timeframe"]["start"]
        sim_end   = community[sys_id]["timeframe"]["end"]
        tz = sim_healthy.timezone[sys_id]

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

        fault_list = sim_faulty.build_fault_list(community[sys_id]["events"])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(f"{sys_id}  |  {sim_start} to {sim_end}")
        ax.set_ylabel("Daily energy ratio (faulty / healthy)")
        ax.set_xlabel("Date")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle("Daily energy ratio", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "power_ratio.png")
    plt.show()


def plot_daily_energy_loss(sim_healthy, sim_faulty, community, save_path=None):
    # bar chart showing total daily energy loss (kWh) per system
    # fault windows are shown as colored background spans so the timing is clear
    # bars are not split by fault — that would require isolated per-fault simulations

    num_systems = len(community)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, community):
        sim_start = community[sys_id]["timeframe"]["start"]
        sim_end   = community[sys_id]["timeframe"]["end"]
        tz = sim_healthy.timezone[sys_id]

        healthy_power = sim_healthy.output[sys_id]
        faulty_power = sim_faulty.output[sys_id]

        daily_healthy_kwh = (healthy_power / 1000).resample("D").sum()
        daily_faulty_kwh = (faulty_power / 1000).resample("D").sum()
        daily_loss_kwh = (daily_healthy_kwh - daily_faulty_kwh).clip(lower=0)

        ax.bar(daily_loss_kwh.index, daily_loss_kwh.values, width=0.8, color="steelblue", alpha=0.8)

        fault_list = sim_faulty.build_fault_list(community[sys_id]["events"])
        legend_entries = [mpatches.Patch(color="steelblue", alpha=0.8, label="energy loss")]
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(f"{sys_id}  |  {sim_start} to {sim_end}")
        ax.set_ylabel("Daily energy loss (kWh)")
        ax.set_xlabel("Date")
        if legend_entries:
            ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle("Daily energy loss from faults", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "daily_energy_loss.png")
    plt.show()


def plot_daily_energy_comparison(sim_healthy, sim_faulty, community, save_path=None):
    # grouped bar chart comparing daily energy (kWh) between healthy and faulty, per system
    # each day has two bars side by side: one for healthy, one for faulty
    # this gives a cleaner view than the hourly timeseries when looking at the full simulation window
    # fault windows are shaded in the background so we can see which bars are affected

    num_systems = len(community)
    fig, axes = plt.subplots(num_systems, 1, figsize=(14, 4 * num_systems), sharex=False)
    if num_systems == 1:
        axes = [axes]

    for ax, sys_id in zip(axes, community):
        sim_start = community[sys_id]["timeframe"]["start"]
        sim_end   = community[sys_id]["timeframe"]["end"]
        tz = sim_healthy.timezone[sys_id]

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

        fault_list = sim_faulty.build_fault_list(community[sys_id]["events"])
        fault_spans(ax, fault_list, sim_start, sim_end, tz, legend_entries)

        ax.set_title(f"{sys_id}  |  {sim_start} to {sim_end}")
        ax.set_ylabel("Daily energy (kWh)")
        ax.set_xlabel("Date")
        ax.legend(handles=legend_entries, loc="upper right", fontsize=8)

    plt.suptitle("Daily energy: healthy vs faulty", fontsize=11)
    plt.tight_layout()
    save_fig(fig, save_path, "daily_energy_comparison.png")
    plt.show()
