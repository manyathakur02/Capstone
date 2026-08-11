"""
src/algorithms/greedy_3d.py
===========================
Greedy First-Fit Baseline Algorithm for 3D SoC Test Scheduling.
Enforces multi-constraint 3D packing across full task execution intervals.
"""

from typing import List
import numpy as np
from src.models.soc_3d import SoC3D, Core3D, ScheduledTask3D, ScheduleResult3D, compute_empirical_constraint_status


class Greedy3DScheduler:
    def __init__(self, soc: SoC3D):
        self.soc = soc

    def optimize(self) -> ScheduleResult3D:
        sorted_cores = sorted(self.soc.cores, key=lambda c: c.test_cycles, reverse=True)

        scheduled_tasks: List[ScheduledTask3D] = []
        completion_events = set([0])

        for core in sorted_cores:
            placed = False

            while not placed:
                candidate_times = sorted(list(completion_events))

                for st in candidate_times:
                    if self.soc.is_placement_valid(scheduled_tasks, core, st):
                        end_t = st + core.test_cycles
                        task = ScheduledTask3D(
                            core_id=core.core_id, core_name=core.name,
                            start_time=st, end_time=end_t, duration=core.test_cycles,
                            power=core.power, tam_width=core.tam_width, layer_id=core.layer_id,
                            grid_x=core.grid_x, grid_y=core.grid_y, tsv_required=core.tsv_required
                        )
                        scheduled_tasks.append(task)
                        completion_events.add(end_t)
                        placed = True
                        break

                if not placed:
                    next_avail = max(completion_events) + 500
                    completion_events.add(next_avail)

        makespan = max(t.end_time for t in scheduled_tasks)
        return self._generate_schedule_result(scheduled_tasks, makespan)

    def _generate_schedule_result(self, tasks: List[ScheduledTask3D], makespan: int) -> ScheduleResult3D:
        time_steps = min(makespan, 200)
        sampled_times = np.linspace(0, makespan, time_steps, dtype=int)

        power_profile, thermal_profile, tsv_profile = [], [], []
        peak_power, peak_temp, max_tsv = 0.0, 0.0, 0

        for t in sampled_times:
            active_t = [task for task in tasks if task.start_time <= t < task.end_time]
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
            algorithm_name="Greedy (Baseline 3D)",
            makespan=makespan,
            tasks=tasks,
            power_profile=power_profile,
            thermal_profile=thermal_profile,
            tsv_profile=tsv_profile,
            peak_power=peak_power,
            peak_temperature=peak_temp,
            max_tsv_used=max_tsv,
            constraint_status=status
        )
