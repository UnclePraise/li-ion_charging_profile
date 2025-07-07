import csv
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import textwrap
from itertools import cycle

# First configuration
config1 = {
    'BATTERY_CAPACITY': 230,
    'CHARGER_EFFICIENCY': 1,
    'CC_FRACTION': 0.80,
    'INITIAL_SOC': 0.447,  # Updated INITIAL_SOC
    'CHARGER_SPEED': 0.20  # Reduced CHARGER_SPEED
}

# Second configuration
config2 = {
    'BATTERY_CAPACITY': 230,
    'CHARGER_EFFICIENCY': 1,
    'CC_FRACTION': 0.80,
    'INITIAL_SOC': 0.458,  # Updated INITIAL_SOC
    'CHARGER_SPEED': 0.20  # Reduced CHARGER_SPEED
}

# Third configuration
config3 = {
    'BATTERY_CAPACITY': 230,
    'CHARGER_EFFICIENCY': 1,
    'CC_FRACTION': 0.80,
    'INITIAL_SOC': 0.536,  # Updated INITIAL_SOC
    'CHARGER_SPEED': 0.20  # Reduced CHARGER_SPEED
}

# Fourth configuration
config4 = {
    'BATTERY_CAPACITY': 230,
    'CHARGER_EFFICIENCY': 1,
    'CC_FRACTION': 0.80,
    'INITIAL_SOC': 0.5052,  # Updated INITIAL_SOC
    'CHARGER_SPEED': 0.20  # Reduced CHARGER_SPEED
}

# Store data for combined overlay plot
all_configs_data = []

# Process each configuration
for config_num, config in enumerate([config1, config2, config3, config4]):
    # Set parameters for current configuration
    BATTERY_CAPACITY = config['BATTERY_CAPACITY']
    CHARGER_EFFICIENCY = config['CHARGER_EFFICIENCY']
    CC_FRACTION = config['CC_FRACTION']
    INITIAL_SOC = config['INITIAL_SOC']

    if 'MAX_POWER' in config:
        MAX_C_RATE = config['MAX_POWER'] / BATTERY_CAPACITY
        AVG_C_RATE = config['AVG_POWER'] / BATTERY_CAPACITY
        CHARGER_SPEEDS = [AVG_C_RATE, MAX_C_RATE]
    else:
        CHARGER_SPEEDS = [config['CHARGER_SPEED']]

    LAMBDA_MIN = 0.1
    LAMBDA_MAX = 20.0
    MAX_ITERATIONS = 100
    TOLERANCE = 0.005
    CC_CV_RATIO = (120-(CC_FRACTION*60))/(CC_FRACTION*60)

    output_base_dir = 'charging_profiles'
    lookup_tables_dir = os.path.join(output_base_dir, 'lookup_tables')
    plots_dir = os.path.join(output_base_dir, 'plots')
    for directory in [output_base_dir, lookup_tables_dir, plots_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)

    all_times = []
    all_grid_loads = []
    all_socs = []
    labels = []

    custom_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for CHARGER_SPEED in CHARGER_SPEEDS:
        print(f"\nProcessing Charger Speed: {CHARGER_SPEED}C")
        CHARGER_OUTPUT_POWER = BATTERY_CAPACITY * CHARGER_SPEED
        TOTAL_TIME = 120 / CHARGER_SPEED

        energy_needed = BATTERY_CAPACITY * (1 - INITIAL_SOC)
        total_energy_grid = energy_needed / CHARGER_EFFICIENCY
        cc_power = CHARGER_OUTPUT_POWER / CHARGER_EFFICIENCY
        cc_energy = total_energy_grid * CC_FRACTION
        cc_time = (cc_energy / cc_power) * 60
        cv_time = CC_CV_RATIO * cc_time
        TOTAL_TIME = cc_time + cv_time

        if cv_time <= 0:
            TOTAL_TIME = cc_time + 1
            cv_time = TOTAL_TIME - cc_time
            print(f"Warning: Total time too short for {CHARGER_SPEED}C. Adjusted TOTAL_TIME to {TOTAL_TIME} minutes to allow for CV phase.")

        lambda_low = LAMBDA_MIN
        lambda_high = LAMBDA_MAX
        lambda_current = (lambda_low + lambda_high) / 2
        iteration = 0

        while iteration < MAX_ITERATIONS:
            grid_loads = []
            for t in np.arange(0, TOTAL_TIME, 1):
                t_hours = t / 60
                cc_time_hours = cc_time / 60
                if t < cc_time:
                    grid_load = cc_power  # Grid load during CC phase
                else:
                    grid_load = cc_power * np.exp(-lambda_current * (t_hours - cc_time_hours))  # Grid load during CV phase
                grid_loads.append(grid_load)

            total_energy = sum(grid_loads) / 60
            energy_diff = total_energy - total_energy_grid

            print(f"Iteration {iteration}: Lambda = {lambda_current:.6f}, Total Energy = {total_energy:.6f}, Difference = {energy_diff:.6f}")

            if abs(energy_diff) <= TOLERANCE:
                break
            elif energy_diff < 0:
                lambda_high = lambda_current
            else:
                lambda_low = lambda_current

            lambda_current = (lambda_low + lambda_high) / 2
            iteration += 1

        if iteration >= MAX_ITERATIONS:
            print(f"Warning: Maximum iterations ({MAX_ITERATIONS}) reached for {CHARGER_SPEED}C. Final Lambda = {lambda_current:.6f}, Energy = {total_energy:.6f}")

        LAMBDA = lambda_current

        print(f"Total Energy from Grid: {total_energy_grid:.6f} kWh")
        print(f"CC Phase Power (Grid): {cc_power:.6f} kW")
        print(f"CC Phase Energy: {cc_energy:.6f} kWh")
        print(f"CC Phase Duration: {cc_time:.6f} minutes")
        print(f"CV Phase Duration: {cv_time:.6f} minutes")
        print(f"Optimized Lambda: {LAMBDA:.6f}")

        times = np.arange(0, TOTAL_TIME, 1)
        grid_loads = []
        socs = []
        cumulative_energy = 0
        for t in times:
            t_hours = t / 60
            cc_time_hours = cc_time / 60
            if t < cc_time:
                grid_load = cc_power
            else:
                grid_load = cc_power * np.exp(-LAMBDA * (t_hours - cc_time_hours))
            energy_step = (grid_load * CHARGER_EFFICIENCY) / 60
            cumulative_energy += energy_step
            soc = INITIAL_SOC * 100 + (cumulative_energy / BATTERY_CAPACITY) * 100
            soc = min(soc, 100.0)
            grid_loads.append(grid_load)
            socs.append(soc)
        
        # Write to CSV in lookup_tables directory
        output_file = os.path.join(lookup_tables_dir, f'Config{config_num+1}_{BATTERY_CAPACITY}kWh_charger_{CHARGER_SPEED}C.csv')
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['time', 'grid_load', 'soc'])
            for t, grid_load, soc in zip(times, grid_loads, socs):
                writer.writerow([t, grid_load, soc])

        plt.figure(figsize=(10, 6))
        ax1 = plt.gca()
        ax1.plot(times, grid_loads, 'b-', label='Grid Load (kW)')
        ax1.set_xlabel('Time (minutes)')
        ax1.set_ylabel('Grid Load (kW)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True)

        ax2 = ax1.twinx()
        ax2.plot(times, socs, 'r--', label='SoC (%)')
        def soc_formatter(x, pos):
            kwh = (x / 100) * BATTERY_CAPACITY
            return f'{x:.1f}% / {kwh:.2f} kWh'
        ax2.yaxis.set_major_formatter(FuncFormatter(soc_formatter))
        ax2.set_ylabel('State of Charge (% / kWh)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.set_ylim(0, 110)
        plt.tight_layout()
        plt.subplots_adjust(left=0.15, right=0.85, top=0.85)

        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')
        plt.title(f'Charging Profile for Config{config_num+1} {BATTERY_CAPACITY} kWh Battery at {CHARGER_SPEED}C')
        plot_file = os.path.join(plots_dir, f'Config{config_num+1}_{BATTERY_CAPACITY}kWh_charger_{CHARGER_SPEED}C.pdf')
        plt.savefig(plot_file, bbox_inches='tight')  # Save as PDF
        plt.close()

        all_times.append(times)
        all_grid_loads.append(grid_loads)
        all_socs.append(socs)
        labels.append(f'{CHARGER_SPEED}C')

    config_data = {
        'times': all_times,
        'grid_loads': all_grid_loads,
        'socs': all_socs,
        'labels': [f'Config{config_num+1} {speed}C' for speed in CHARGER_SPEEDS]
    }
    all_configs_data.append(config_data)

# Overlay plot for all configurations
plt.figure(figsize=(14, 9))
ax1 = plt.gca()

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
color_cycle = cycle(colors)

max_grid_load = 0
for config_data in all_configs_data:
    for grid_loads in config_data['grid_loads']:
        max_grid_load = max(max_grid_load, max(grid_loads))

for config_data in all_configs_data:
    for times, grid_loads, label in zip(config_data['times'], 
                                        config_data['grid_loads'], 
                                        config_data['labels']):
        ax1.plot(times, grid_loads, '-', 
                 label=f'Grid Load {label}', 
                 color=next(color_cycle))

ax1.set_xlabel('Time (minutes)')
ax1.set_ylabel('Grid Load (kW)', color='k')
ax1.tick_params(axis='y', labelcolor='k')
ax1.grid(True)
ax1.set_ylim(0, max_grid_load * 1.1)

ax2 = ax1.twinx()
color_cycle = cycle(colors)
for config_data in all_configs_data:
    for times, socs, label in zip(config_data['times'], 
                                  config_data['socs'], 
                                  config_data['labels']):
        ax2.plot(times, socs, '--', 
                 label=f'SoC {label}', 
                 color=next(color_cycle))
def soc_formatter(x, pos):
    kwh = (x / 100) * BATTERY_CAPACITY
    return f'{x:.1f}% / {kwh:.2f} kWh'
ax2.yaxis.set_major_formatter(FuncFormatter(soc_formatter))
ax2.set_ylabel('State of Charge (% / kWh)', color='k')
ax2.tick_params(axis='y', labelcolor='k')
ax2.set_ylim(0, 110)

title = f'Charging Profiles Overlay for {BATTERY_CAPACITY} kWh Battery'
wrapped_title = '\n'.join(textwrap.wrap(title, width=50))
plt.title(wrapped_title)

plt.tight_layout()
plt.subplots_adjust(right=0.85, top=0.85, bottom=0.2)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
plt.legend(lines1 + lines2, labels1 + labels2, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=4)

plot_file_overlay = os.path.join(plots_dir, f'{BATTERY_CAPACITY}kWh_charger_overlay.pdf')
plt.savefig(plot_file_overlay, bbox_inches='tight')
plt.close()

print(f"\nOverlay plot saved to {plot_file_overlay}")