"""
2d/src/algorithms/bat_2d.py
===========================
Bat Algorithm (Bat 2D) Test Scheduling Algorithm.
Base Reference Paper: A. K. Singh & S. K. Singh (IEEE TVLSI 2022) [Paper 4].
"""

import math
import random
from typing import List, Tuple
import numpy as np

from src.models.soc_2d import SoC2D, Core2D, ScheduledTask2D, ScheduleResult2D
from src.constraints.vlsi_constraints_2d import verify_2d_vlsi_constraints


class Bat2DScheduler:
    def __init__(self, soc: SoC2D, num_bats: int = 15, max_iterations: int = 15):
        self.soc = soc
        self.num_bats = num_bats
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
        population = []
        for _ in range(self.num_bats):
            perm = self.soc.cores.copy()
            random.shuffle(perm)
            ms, tasks = self._build_schedule(perm)
            population.append({
                "perm": perm, "makespan": ms, "tasks": tasks,
                "frequency": 0.0, "loudness": 1.0, "pulse_rate": 0.5
            })

        best_bat = min(population, key=lambda b: b["makespan"])

        for t_iter in range(self.max_iterations):
            for i in range(self.num_bats):
                freq = random.uniform(0, 1)
                population[i]["frequency"] = freq

                new_perm = population[i]["perm"].copy()
                if random.random() > population[i]["pulse_rate"]:
                    # Local random walk around best
                    new_perm = best_bat["perm"].copy()
                    idx1, idx2 = random.sample(range(len(new_perm)), 2)
                    new_perm[idx1], new_perm[idx2] = new_perm[idx2], new_perm[idx1]
                else:
                    idx1, idx2 = random.sample(range(len(new_perm)), 2)
                    new_perm[idx1], new_perm[idx2] = new_perm[idx2], new_perm[idx1]

                new_ms, new_tasks = self._build_schedule(new_perm)

                if new_ms <= population[i]["makespan"] and random.random() < population[i]["loudness"]:
                    population[i]["perm"] = new_perm
                    population[i]["makespan"] = new_ms
                    population[i]["tasks"] = new_tasks
                    population[i]["loudness"] *= 0.95
                    population[i]["pulse_rate"] = 0.5 * (1 - math.exp(-0.05 * t_iter))

                if population[i]["makespan"] < best_bat["makespan"]:
                    best_bat = population[i]

        makespan = best_bat["makespan"]
        tasks = best_bat["tasks"]

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
            algorithm_name="Bat 2D Algorithm",
            makespan=makespan,
            tasks=tasks,
            power_profile=power_profile,
            tam_profile=tam_profile,
            peak_power=peak_power,
            max_tam_used=max_tam,
            constraint_status=status
        )
