"""
2d/src/algorithms/firefly_2d.py
===============================
Firefly Algorithm (Firefly 2D) Test Scheduling Algorithm.
Base Reference Paper: G. Chandrasekaran et al. (Revue d'Intelligence Artificielle 2021) [Paper 1].
"""

import random
from typing import List, Tuple
import numpy as np

from src.models.soc_2d import SoC2D, Core2D, ScheduledTask2D, ScheduleResult2D
from src.constraints.vlsi_constraints_2d import verify_2d_vlsi_constraints


class Firefly2DScheduler:
    def __init__(self, soc: SoC2D, num_fireflies: int = 15, max_iterations: int = 15):
        self.soc = soc
        self.num_fireflies = num_fireflies
        self.max_iterations = max_iterations

    def _build_schedule(self, permutation: List[Core2D]) -> Tuple[int, List[ScheduledTask2D]]:
        scheduled_tasks: List[ScheduledTask2D] = []
        for core in permutation:
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
        return makespan, scheduled_tasks

    def optimize(self) -> ScheduleResult2D:
        fireflies = []
        for _ in range(self.num_fireflies):
            perm = self.soc.cores.copy()
            random.shuffle(perm)
            ms, tasks = self._build_schedule(perm)
            fireflies.append({"perm": perm, "makespan": ms, "tasks": tasks})

        best_firefly = min(fireflies, key=lambda f: f["makespan"])

        for _ in range(self.max_iterations):
            for i in range(self.num_fireflies):
                for j in range(self.num_fireflies):
                    if fireflies[j]["makespan"] < fireflies[i]["makespan"]:
                        # Move firefly i toward brighter firefly j
                        new_perm = fireflies[j]["perm"].copy()
                        if random.random() < 0.3:
                            idx1, idx2 = random.sample(range(len(new_perm)), 2)
                            new_perm[idx1], new_perm[idx2] = new_perm[idx2], new_perm[idx1]

                        new_ms, new_tasks = self._build_schedule(new_perm)
                        if new_ms < fireflies[i]["makespan"]:
                            fireflies[i] = {"perm": new_perm, "makespan": new_ms, "tasks": new_tasks}

            curr_best = min(fireflies, key=lambda f: f["makespan"])
            if curr_best["makespan"] < best_firefly["makespan"]:
                best_firefly = curr_best

        makespan = best_firefly["makespan"]
        tasks = best_firefly["tasks"]

        time_steps = min(makespan, 200)
        sampled_times = np.linspace(0, makespan, time_steps, dtype=int)
        power_profile, tam_profile = [], []
        peak_power, max_tam = 0.0, 0

        for t in sampled_times:
            active_t = [tk for tk in tasks if tk.start_time <= t < tk.end_time]
            inst_p = sum(tk.power for tk in active_t)
            inst_tam = sum(tk.tam_width for tk in active_t)

            power_profile.append(inst_p)
            tam_profile.append(inst_tam)

            peak_power = max(peak_power, inst_p)
            max_tam = max(max_tam, inst_tam)

        _, status = verify_2d_vlsi_constraints(peak_power, self.soc.max_power, max_tam, self.soc.max_tam_width)

        return ScheduleResult2D(
            algorithm_name="Firefly 2D Algorithm",
            makespan=makespan,
            tasks=tasks,
            power_profile=power_profile,
            tam_profile=tam_profile,
            peak_power=peak_power,
            max_tam_used=max_tam,
            constraint_status=status
        )
