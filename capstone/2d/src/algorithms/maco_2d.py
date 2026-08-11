"""
2d/src/algorithms/maco_2d.py
============================
Modified Ant Colony Optimization (MACO 2D) Test Scheduling Algorithm.
Base Reference Paper: L. Zheng & Q. Xu (ACM TODAES 2024) [Paper 14].
"""

import random
from typing import List, Tuple
import numpy as np

from src.models.soc_2d import SoC2D, Core2D, ScheduledTask2D, ScheduleResult2D
from src.constraints.vlsi_constraints_2d import verify_2d_vlsi_constraints


class MACO2DScheduler:
    def __init__(self, soc: SoC2D, num_ants: int = 15, max_iterations: int = 15):
        self.soc = soc
        self.num_ants = num_ants
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
        num_cores = len(self.soc.cores)
        pheromones = np.ones((num_cores, num_cores))
        best_perm = None
        best_makespan = float('inf')
        best_tasks = []

        alpha = 1.0
        beta = 2.0
        evaporation_rate = 0.1

        for iter_idx in range(self.max_iterations):
            # Dynamic Ant Population Scaling
            active_ants = max(5, int(self.num_ants * (1.0 - 0.3 * (iter_idx / self.max_iterations))))

            for _ in range(active_ants):
                unassigned = self.soc.cores.copy()
                perm = []
                current_core = random.choice(unassigned)
                perm.append(current_core)
                unassigned.remove(current_core)

                while unassigned:
                    last_idx = current_core.core_id - 1
                    probs = []
                    for cand in unassigned:
                        cand_idx = cand.core_id - 1
                        tau = pheromones[last_idx, cand_idx] ** alpha
                        eta = (1.0 / (cand.test_cycles + 1)) ** beta
                        probs.append(tau * eta)

                    prob_sum = sum(probs)
                    if prob_sum > 0:
                        norm_probs = [p / prob_sum for p in probs]
                        next_core = np.random.choice(unassigned, p=norm_probs)
                    else:
                        next_core = random.choice(unassigned)

                    perm.append(next_core)
                    unassigned.remove(next_core)
                    current_core = next_core

                ms, tasks = self._build_schedule(perm)
                if ms < best_makespan:
                    best_makespan = ms
                    best_perm = perm
                    best_tasks = tasks

            # Pheromone Evaporation & Elite Reinforcement
            pheromones *= (1.0 - evaporation_rate)
            delta_tau = 1.0 / (best_makespan + 1)
            for i in range(len(best_perm) - 1):
                idx1 = best_perm[i].core_id - 1
                idx2 = best_perm[i+1].core_id - 1
                pheromones[idx1, idx2] += delta_tau

        makespan = best_makespan
        tasks = best_tasks

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
            algorithm_name="Modified ACO (MACO 2D)",
            makespan=makespan,
            tasks=tasks,
            power_profile=power_profile,
            tam_profile=tam_profile,
            peak_power=peak_power,
            max_tam_used=max_tam,
            constraint_status=status
        )
