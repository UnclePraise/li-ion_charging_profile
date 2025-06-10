import csv
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import textwrap

# Custom parameters (modify these as needed)
BATTERY_CAPACITY = 230  # kWh
CHARGER_EFFICIENCY = 1  # Charger efficiency
CC_FRACTION = 0.80  # Fraction of energy delivered in CC phase

# Define charger speeds based on power levels (20 kW to 60 kW)
MIN_POWER = 20  # Minimum power in kW
MAX_POWER = 60  # Maximum power in kW
STEP_POWER = 10  # Step size in kW

# Calculate corresponding C-rates for each power level
CHARGER_SPEEDS = [power / BATTERY_CAPACITY for power in range(MIN_POWER, MAX_POWER + STEP_POWER, STEP_POWER)]

# print(f"Charger speeds (C-rates): {CHARGER_SPEEDS}")

# Constants for charging profile generation (do not modify)
LAMBDA_MIN = 0.1  # Minimum lambda value
LAMBDA_MAX = 20.0  # Maximum lambda value
MAX_ITERATIONS = 100  # Maximum number of iterations
TOLERANCE = 0.005  # Tolerance for energy match (within 2 dp)
CC_CV_RATIO = (120-(CC_FRACTION*60))/(CC_FRACTION*60)  # Ratio of CC to CV phase durations

# Define output directories and ensure they exist
output_base_dir = 'charging_profiles'
lookup_tables_dir = os.path.join(output_base_dir, 'lookup_tables')
plots_dir = os.path.join(output_base_dir, 'plots')
for directory in [output_base_dir, lookup_tables_dir, plots_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Store data for combined plot
all_times = []
all_grid_loads = []
all_socs = []
labels = []

# Define custom colors for better differentiation
custom_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']  # Tableau-inspired colors

# Process each charger speed
for CHARGER_SPEED in CHARGER_SPEEDS:
    print(f"\nProcessing Charger Speed: {CHARGER_SPEED}C")
    
    # Calculate charger output power and total time
    CHARGER_OUTPUT_POWER = BATTERY_CAPACITY * CHARGER_SPEED  # kW
    TOTAL_TIME = 120 / CHARGER_SPEED  # Total charging time in minutes
    
    # Calculate initial parameters
    total_energy_grid = BATTERY_CAPACITY / CHARGER_EFFICIENCY  # Target energy from grid (kWh)
    cc_power = CHARGER_OUTPUT_POWER / CHARGER_EFFICIENCY  # CC phase power in kW (grid power)
    cc_energy = total_energy_grid * CC_FRACTION  # Energy delivered in CC phase (kWh)
    cc_time = (cc_energy / cc_power) * 60  # CC phase duration in minutes
    cv_time = CC_CV_RATIO * cc_time  # CV phase duration in minutes
    TOTAL_TIME = cc_time + cv_time  # Total time in minutes
    
    # Validate CV time
    if cv_time <= 0:
        TOTAL_TIME = cc_time + 1  # Ensure CV phase has at least 1 minute
        cv_time = TOTAL_TIME - cc_time
        print(f"Warning: Total time too short for {CHARGER_SPEED}C. Adjusted TOTAL_TIME to {TOTAL_TIME} minutes to allow for CV phase.")
    
    # Iterative adjustment of LAMBDA
    lambda_low = LAMBDA_MIN
    lambda_high = LAMBDA_MAX
    lambda_current = (lambda_low + lambda_high) / 2  # Initial midpoint
    iteration = 0
    
    while iteration < MAX_ITERATIONS:
        # Generate temporary grid load data
        grid_loads = []
        for t in np.arange(0, TOTAL_TIME, 1):  # Time in minutes
            t_hours = t / 60  # Convert to hours
            cc_time_hours = cc_time / 60
            if t < cc_time:
                grid_load = cc_power
            else:
                grid_load = cc_power * np.exp(-lambda_current * (t_hours - cc_time_hours))
            grid_loads.append(grid_load)
    
        # Calculate total energy
        total_energy = sum(grid_loads) / 60  # Convert sum of power (kW) over minutes to energy (kWh)
        energy_diff = total_energy - total_energy_grid
    
        # Print current iteration details
        print(f"Iteration {iteration}: Lambda = {lambda_current:.6f}, Total Energy = {total_energy:.6f}, Difference = {energy_diff:.6f}")
    
        # Adjust lambda based on energy difference
        if abs(energy_diff) <= TOLERANCE:
            break
        elif energy_diff < 0:  # Energy too low, decrease lambda (slower decay)
            lambda_high = lambda_current
        else:  # Energy too high, increase lambda (faster decay)
            lambda_low = lambda_current
    
        lambda_current = (lambda_low + lambda_high) / 2
        iteration += 1
    
    if iteration >= MAX_ITERATIONS:
        print(f"Warning: Maximum iterations ({MAX_ITERATIONS}) reached for {CHARGER_SPEED}C. Final Lambda = {lambda_current:.6f}, Energy = {total_energy:.6f}")
    
    # Use the final lambda value
    LAMBDA = lambda_current
    
    # Print final parameters
    print(f"Total Energy from Grid: {total_energy_grid:.6f} kWh")
    print(f"CC Phase Power (Grid): {cc_power:.6f} kW")
    print(f"CC Phase Energy: {cc_energy:.6f} kWh")
    print(f"CC Phase Duration: {cc_time:.6f} minutes")
    print(f"CV Phase Duration: {cv_time:.6f} minutes")
    print(f"Optimized Lambda: {LAMBDA:.6f}")
    
    # Generate charging profile data for CSV and plot
    times = np.arange(0, TOTAL_TIME, 1)  # Time in minutes
    grid_loads = []
    socs = []
    cumulative_energy = 0
    for t in times:
        t_hours = t / 60  # Convert to hours
        cc_time_hours = cc_time / 60
        if t < cc_time:
            grid_load = cc_power
        else:
            grid_load = cc_power * np.exp(-LAMBDA * (t_hours - cc_time_hours))
        
        # Calculate energy delivered to battery in this time step (kWh)
        energy_step = (grid_load * CHARGER_EFFICIENCY) / 60  # kWh for 1 minute
        cumulative_energy += energy_step
        
        # Calculate SoC as a percentage
        soc = (cumulative_energy / BATTERY_CAPACITY) * 100  # SoC in percent
        soc = min(soc, 100.0)  # Cap SoC at 100%
        
        grid_loads.append(grid_load)
        socs.append(soc)
    
    # Write to CSV in lookup_tables directory
    output_file = os.path.join(lookup_tables_dir, f'{BATTERY_CAPACITY}kWh_charger_{CHARGER_SPEED}C.csv')
    with open(output_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['time', 'grid_load', 'soc'])
        for t, grid_load, soc in zip(times, grid_loads, socs):
            writer.writerow([t, grid_load, soc])
    
    # Create individual plot
    plt.figure(figsize=(10, 6))
    ax1 = plt.gca()
    ax1.plot(times, grid_loads, 'b-', label='Grid Load (kW)')
    ax1.set_xlabel('Time (minutes)')
    ax1.set_ylabel('Grid Load (kW)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.grid(True)
    
    ax2 = ax1.twinx()
    ax2.plot(times, socs, 'r--', label='SoC (%)')  # Dotted line for SoC
    def soc_formatter(x, pos):
        kwh = (x / 100) * BATTERY_CAPACITY
        return f'{x:.1f}% / {kwh:.2f} kWh'
    ax2.yaxis.set_major_formatter(FuncFormatter(soc_formatter))
    ax2.set_ylabel('State of Charge (% / kWh)', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    ax2.set_ylim(0, 110)  # Extend y-axis to ensure full visibility
    plt.tight_layout()
    plt.subplots_adjust(left=0.15, right=0.85, top=0.85)  # Adjust margins for labels and title
    
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    plt.title(f'Charging Profile for {BATTERY_CAPACITY} kWh Battery at {CHARGER_SPEED}C')
    plot_file = os.path.join(plots_dir, f'{BATTERY_CAPACITY}kWh_charger_{CHARGER_SPEED}C.pdf')
    plt.savefig(plot_file, bbox_inches='tight')  # Save as PDF
    plt.close()
    
    # Store data for combined plot
    all_times.append(times)
    all_grid_loads.append(grid_loads)
    all_socs.append(socs)
    labels.append(f'{CHARGER_SPEED}C')

# Create combined plot
plt.figure(figsize=(14, 9))  # Larger figure size for better visibility
ax1 = plt.gca()
for times, grid_loads, label, color in zip(all_times, all_grid_loads, labels, custom_colors[:len(CHARGER_SPEEDS)]):
    ax1.plot(times, grid_loads, '-', label=f'Grid Load {label}', color=color)
ax1.set_xlabel('Time (minutes)')
ax1.set_ylabel('Grid Load (kW)', color='k')
ax1.tick_params(axis='y', labelcolor='k')
ax1.grid(True)
ax1.set_ylim(0, max([max(loads) for loads in all_grid_loads]) * 1.1)  # Adjust y-axis limit

ax2 = ax1.twinx()
for times, socs, label, color in zip(all_times, all_socs, labels, custom_colors[:len(CHARGER_SPEEDS)]):
    ax2.plot(times, socs, '--', label=f'SoC {label}', color=color)  # Dotted line for SoC
def soc_formatter(x, pos):
    kwh = (x / 100) * BATTERY_CAPACITY
    return f'{x:.1f}% / {kwh:.2f} kWh'
ax2.yaxis.set_major_formatter(FuncFormatter(soc_formatter))
ax2.set_ylabel('State of Charge (% / kWh)', color='k')
ax2.tick_params(axis='y', labelcolor='k')
ax2.set_ylim(0, 110)  # Extend y-axis to ensure full visibility

# Wrap title to prevent it from being too wide
title = f'Charging Profiles for {BATTERY_CAPACITY} kWh Battery at Multiple Charger Speeds'
wrapped_title = '\n'.join(textwrap.wrap(title, width=50))
plt.title(wrapped_title)

# Adjust layout and margins
plt.tight_layout()
plt.subplots_adjust(right=0.85, top=0.85, bottom=0.2)  # Increase top margin and leave space at bottom for legend

# Combine legends and move below the plot
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
plt.legend(lines1 + lines2, labels1 + labels2, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=4)

plot_file = os.path.join(plots_dir, f'{BATTERY_CAPACITY}kWh_charger_combined.pdf')
plt.savefig(plot_file, bbox_inches='tight')  # Save as PDF
plt.close()

print(f"\nCombined plot saved to {plot_file}")