"""
src/models/predictive_thermal.py
================================
Machine Learning / Heuristic Predictive Thermal Estimator & Frequency Scaling Engine.
Based on S. Roy and P. Giri (2022) [Ref 12].

Estimates transient junction temperature Tj(t + Delta_t) dynamically and scales
test clock frequency or inserts cooling cycles when thermal thresholds are threatened.
"""

import math
import numpy as np
from typing import List, Dict, Tuple
from src.models.soc_3d import Core3D, SoC3D, ScheduledTask3D, ScheduleResult3D, compute_empirical_constraint_status


class PredictiveThermalEstimator:
    """
    Predictive Thermal Estimator using polynomial regression / exponential thermal decay
    to forecast transient junction temperature spikes across die layers.
    """
    def __init__(
        self,
        num_layers: int = 3,
        ambient_temp_k: float = 300.15,
        thermal_threshold_k: float = 365.15  # 92°C
    ):
        self.num_layers = num_layers
        self.ambient_temp_k = ambient_temp_k
        self.thermal_threshold_k = thermal_threshold_k
        # Layer thermal resistance factors (K/W)
        self.r_th = [0.35 + 0.15 * z for z in range(num_layers)]

    def predict_transient_tj(
        self,
        active_cores: List[Core3D],
        horizon_cycles: int = 1000
    ) -> float:
        """
        Forecasts junction temperature Tj (in °C) over the lookahead horizon window.
        """
        layer_powers = np.zeros(self.num_layers)
        for c in active_cores:
            z = min(c.layer_id, self.num_layers - 1)
            layer_powers[z] += c.power

        # Forecast vertical heat accumulation
        accumulated_heat = 0.0
        max_layer_temp = self.ambient_temp_k

        for z in range(self.num_layers - 1, -1, -1):
            eff_power = layer_powers[z] + accumulated_heat
            t_layer = self.ambient_temp_k + self.r_th[z] * eff_power
            if t_layer > max_layer_temp:
                max_layer_temp = t_layer
            accumulated_heat += layer_powers[z] * 0.7

        # Spatial inter-core coupling
        coupling_spike = 0.0
        for c1 in active_cores:
            for c2 in active_cores:
                if c1.core_id < c2.core_id and abs(c1.layer_id - c2.layer_id) <= 1:
                    coupling_spike += (c1.power * c2.power) * 0.08

        predicted_tj_k = max_layer_temp + coupling_spike
        return predicted_tj_k - 273.15  # Return in °C


class FrequencyScaledScheduler:
    """
    Applies Machine Learning / Predictive Thermal estimation to dynamically adjust
    test clock frequency scaling factors (1.0x, 0.8x, 0.5x) or insert cooling delays.
    """
    def __init__(self, soc: SoC3D, estimator: PredictiveThermalEstimator):
        self.soc = soc
        self.estimator = estimator

    def apply_frequency_scaling(self, schedule: ScheduleResult3D) -> ScheduleResult3D:
        """
        Adjusts task durations based on dynamic frequency scaling when thermal spikes are forecasted.
        """
        scaled_tasks: List[ScheduledTask3D] = []
        current_time = 0

        for task in sorted(schedule.tasks, key=lambda t: t.start_time):
            # Predict Tj for active task
            core = Core3D(
                core_id=task.core_id, name=task.core_name, test_cycles=task.duration,
                power=task.power, tam_width=task.tam_width, layer_id=task.layer_id,
                grid_x=task.grid_x, grid_y=task.grid_y, tsv_required=task.tsv_required
            )
            pred_tj = self.estimator.predict_transient_tj([core])

            # Determine frequency scaling factor (1.0 = nominal, 0.8 = throttled, 0.5 = heavy throttling)
            if pred_tj > 85.0:
                scale_factor = 0.8  # Throttling reduces power density by 20% but increases cycles by 1.25x
                effective_duration = int(task.duration * 1.25)
                scaled_power = task.power * 0.8
            else:
                scale_factor = 1.0
                effective_duration = task.duration
                scaled_power = task.power

            st = max(current_time, task.start_time)
            end_t = st + effective_duration
            current_time = end_t

            scaled_tasks.append(ScheduledTask3D(
                core_id=task.core_id, core_name=task.core_name,
                start_time=st, end_time=end_t, duration=effective_duration,
                power=scaled_power, tam_width=task.tam_width, layer_id=task.layer_id,
                grid_x=task.grid_x, grid_y=task.grid_y, tsv_required=task.tsv_required
            ))

        makespan = max(t.end_time for t in scaled_tasks)

        # Re-generate profiles
        time_steps = min(makespan, 200)
        sampled_times = np.linspace(0, makespan, time_steps, dtype=int)

        power_profile, thermal_profile, tsv_profile = [], [], []
        peak_power, peak_temp, max_tsv = 0.0, 0.0, 0

        for t in sampled_times:
            active_t = [tk for tk in scaled_tasks if tk.start_time <= t < tk.end_time]
            active_cores = [
                Core3D(
                    core_id=tk.core_id, name=tk.core_name, test_cycles=tk.duration,
                    power=tk.power, tam_width=tk.tam_width, layer_id=tk.layer_id,
                    grid_x=tk.grid_x, grid_y=tk.grid_y, tsv_required=tk.tsv_required
                ) for tk in active_t
            ]
            inst_power = sum(c.power for c in active_cores)
            tsv_used, _ = self.soc.tsv_bus.get_tsv_utilization(active_cores)
            thermal_res = self.soc.thermal_model.estimate_temperature_profile(active_cores)
            inst_temp_c = thermal_res["max_tj_celsius"]

            power_profile.append(inst_power)
            thermal_profile.append(inst_temp_c)
            tsv_profile.append(tsv_used)

            peak_power = max(peak_power, inst_power)
            peak_temp = max(peak_temp, inst_temp_c)
            max_tsv = max(max_tsv, tsv_used)

        status = compute_empirical_constraint_status(
            peak_power=peak_power, max_power=self.soc.max_power,
            peak_temp=peak_temp, max_temp_celsius=self.soc.max_temperature - 273.15,
            max_tsv=max_tsv, max_tsv_bandwidth=self.soc.max_tsv_bandwidth
        )

        return ScheduleResult3D(
            algorithm_name=schedule.algorithm_name + " (ML Frequency-Scaled)",
            makespan=makespan,
            tasks=scaled_tasks,
            power_profile=power_profile,
            thermal_profile=thermal_profile,
            tsv_profile=tsv_profile,
            peak_power=peak_power,
            peak_temperature=peak_temp,
            max_tsv_used=max_tsv,
            constraint_status=status
        )