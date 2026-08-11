"""
2d/src/algorithms/abc_2d.py
===========================
Artificial Bee Colony (ABC 2D) Test Scheduling Algorithm.
"""

import random
from typing import List, Tuple
import numpy as np

from src.models.soc_2d import SoC2D, Core2D, ScheduledTask2D, ScheduleResult2D
from src.constraints.vlsi_constraints_2d import verify_2d_vlsi_constraints


class ABC2DScheduler:
    def __init__(self, soc: SoC2D, colony_size: int = 15, max_iterations: int = 15):
        self.soc = soc
        self.colony_size = colony_size
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
        num_foods = self.colony_size
        foods = []

        for _ in range(num_foods):
            perm = self.soc.cores.copy()
            random.shuffle(perm)
            ms, tasks = self._build_schedule(perm)
            foods.append({"perm": perm, "makespan": ms, "tasks": tasks, "trial": 0})

        best_food = min(foods, key=lambda f: f["makespan"])

        for _ in range(self.max_iterations):
            # Employed Bees
            for i in range(num_foods):
                k = random.choice([idx for idx in range(num_foods) if idx != i])
                new_perm = foods[i]["perm"].copy()
                idx1, idx2 = random.sample(range(len(new_perm)), 2)
                new_perm[idx1], new_perm[idx2] = new_perm[idx2], new_perm[idx1]

                new_ms, new_tasks = self._build_schedule(new_perm)
                if new_ms <= foods[i]["makespan"]:
                    foods[i] = {"perm": new_perm, "makespan": new_ms, "tasks": new_tasks, "trial": 0}
                else:
                    foods[i]["trial"] += 1

            # Onlooker Bees
            fitnesses = [1.0 / (f["makespan"] + 1) for f in foods]
            total_fit = sum(fitnesses)
            probs = [fit / total_fit for fit in fitnesses]

            for _ in range(num_foods):
                i = np.random.choice(num_foods, p=probs)
                new_perm = foods[i]["perm"].copy()
                idx1, idx2 = random.sample(range(len(new_perm)), 2)
                new_perm[idx1], new_perm[idx2] = new_perm[idx2], new_perm[idx1]

                new_ms, new_tasks = self._build_schedule(new_perm)
                if new_ms <= foods[i]["makespan"]:
                    foods[i] = {"perm": new_perm, "makespan": new_ms, "tasks": new_tasks, "trial": 0}
                else:
                    foods[i]["trial"] += 1

            # Scout Bees
            for i in range(num_foods):
                if foods[i]["trial"] > 5:
                    perm = self.soc.cores.copy()
                    random.shuffle(perm)
                    ms, tasks = self._build_schedule(perm)
                    foods[i] = {"perm": perm, "makespan": ms, "tasks": tasks, "trial": 0}

            curr_best = min(foods, key=lambda f: f["makespan"])
            if curr_best["makespan"] < best_food["makespan"]:
                best_food = curr_best

        makespan = best_food["makespan"]
        tasks = best_food["tasks"]

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
            algorithm_name="Artificial Bee Colony (ABC 2D)",
            makespan=makespan,
            tasks=tasks,
            power_profile=power_profile,
            tam_profile=tam_profile,
            peak_power=peak_power,
            max_tam_used=max_tam,
            constraint_status=status
        )
