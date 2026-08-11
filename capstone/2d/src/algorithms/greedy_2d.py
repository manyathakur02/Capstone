"""
2d/src/algorithms/greedy_2d.py
==============================
Greedy 2D Test Scheduling Baseline Algorithm (LPT - Longest Processing Time First).
Base Reference Paper: Iyengar, Chakrabarty, & Marinissen (IEEE TCAD 2002).
"""

from typing import List
import numpy as np
from src.models.soc_2d import SoC2D, Core2D, ScheduledTask2D, ScheduleResult2D
from src.constraints.vlsi_constraints_2d import verify_2d_vlsi_constraints


class Greedy2DScheduler:
    def __init__(self, soc: SoC2D):
        self.soc = soc

    def optimize(self) -> ScheduleResult2D:
        sorted_cores = sorted(self.soc.cores, key=lambda c: c.test_cycles, reverse=True)
        scheduled_tasks: List[ScheduledTask2D] = []

        for core in sorted_cores:
            st = 0
            while True:
                if self.soc.is_placement_valid(scheduled_tasks, core, st):
                    break
                st += 100

            et = st + core.test_cycles
            scheduled_tasks.append(ScheduledTask2D(
                core_id=core.core_id, core_name=core.name,
                start_time=st, end_time=et, duration=core.test_cycles,
                power=core.power, tam_width=core.tam_width,
                grid_x=core.grid_x, grid_y=core.grid_y
            ))

        makespan = max(t.end_time for t in scheduled_tasks)

        # Generate profiles
        time_steps = min(makespan, 200)
        sampled_times = np.linspace(0, makespan, time_steps, dtype=int)
        power_profile, tam_profile = [], []
        peak_power, max_tam = 0.0, 0

        for t in sampled_times:
            active_t = [tk for tk in scheduled_tasks if tk.start_time <= t < tk.end_time]
            inst_p = sum(tk.power for tk in active_t)
            inst_tam = sum(tk.tam_width for tk in active_t)

            power_profile.append(inst_p)
            tam_profile.append(inst_tam)

            peak_power = max(peak_power, inst_p)
            max_tam = max(max_tam, inst_tam)

        _, status = verify_2d_vlsi_constraints(peak_power, self.soc.max_power, max_tam, self.soc.max_tam_width)

        return ScheduleResult2D(
            algorithm_name="Greedy 2D Baseline",
            makespan=makespan,
            tasks=scheduled_tasks,
            power_profile=power_profile,
            tam_profile=tam_profile,
            peak_power=peak_power,
            max_tam_used=max_tam,
            constraint_status=status
        )
