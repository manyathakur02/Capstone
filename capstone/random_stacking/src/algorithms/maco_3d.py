"""
src/algorithms/maco_3d.py
=========================
3D-Aware Modified Ant Colony Optimization (MACO) for 3D SoC Test Scheduling.
Enforces multi-constraint 3D packing across full task execution intervals.
"""

import math
import random
import numpy as np
from typing import List, Tuple
from src.models.soc_3d import SoC3D, Core3D, ScheduledTask3D, ScheduleResult3D, compute_empirical_constraint_status


class MACO3DScheduler:
    def __init__(
        self,
        soc: SoC3D,
        num_ants: int = 25,
        max_iterations: int = 35,
        alpha: float = 1.0,
        beta: float = 2.0,
        evaporation_rate: float = 0.15,
        q_value: float = 100.0,
        dynamic_scaling: bool = True
    ):
        self.soc = soc
        self.num_ants = num_ants
        self.max_iterations = max_iterations
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate
        self.q_value = q_value
        self.dynamic_scaling = dynamic_scaling

        self.num_cores = len(soc.cores)
        self.pheromone = np.full((self.num_cores, self.num_cores), 1.0)

    def _compute_heuristics(self) -> np.ndarray:
        eta = np.zeros((self.num_cores, self.num_cores))
        for i, c1 in enumerate(self.soc.cores):
            for j, c2 in enumerate(self.soc.cores):
                if i != j:
                    cycle_weight = c2.test_cycles / 10000.0
                    power_weight = 1.0 / (c2.power + 0.1)
                    layer_factor = 1.2 if c2.layer_id == 0 else 1.0
                    eta[i][j] = (cycle_weight * 0.6 + power_weight * 0.4) * layer_factor
        return eta

    def _construct_ant_schedule(self, eta: np.ndarray, current_ants: int) -> Tuple[int, List[ScheduledTask3D]]:
        unscheduled_cores = list(range(self.num_cores))
        first_idx = random.choice(unscheduled_cores)
        ordered_cores = [first_idx]
        unscheduled_cores.remove(first_idx)

        while unscheduled_cores:
            last_idx = ordered_cores[-1]
            probs = []
            for candidate_idx in unscheduled_cores:
                tau = self.pheromone[last_idx][candidate_idx] ** self.alpha
                eta_val = eta[last_idx][candidate_idx] ** self.beta
                probs.append(tau * eta_val)

            total_prob = sum(probs)
            if total_prob == 0 or np.isnan(total_prob):
                next_idx = random.choice(unscheduled_cores)
            else:
                norm_probs = [p / total_prob for p in probs]
                next_idx = np.random.choice(unscheduled_cores, p=norm_probs)

            ordered_cores.append(next_idx)
            unscheduled_cores.remove(next_idx)

        scheduled_tasks: List[ScheduledTask3D] = []
        completion_events = set([0])

        for core_idx in ordered_cores:
            core = self.soc.cores[core_idx]
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
        return makespan, scheduled_tasks

    def optimize(self) -> ScheduleResult3D:
        eta = self._compute_heuristics()
        best_makespan = float('inf')
        best_tasks: List[ScheduledTask3D] = []

        for iteration in range(self.max_iterations):
            if self.dynamic_scaling:
                current_ants = int(self.num_ants * (1.0 + 0.3 * math.sin(math.pi * iteration / self.max_iterations)))
            else:
                current_ants = self.num_ants

            ant_schedules = []
            for _ in range(current_ants):
                makespan, tasks = self._construct_ant_schedule(eta, current_ants)
                ant_schedules.append((makespan, tasks))

                if makespan < best_makespan:
                    best_makespan = makespan
                    best_tasks = tasks

            self.pheromone = (1.0 - self.evaporation_rate) * self.pheromone

            for makespan, tasks in ant_schedules:
                delta_tau = self.q_value / float(makespan)
                for k in range(len(tasks) - 1):
                    c1_idx = tasks[k].core_id - 1
                    c2_idx = tasks[k+1].core_id - 1
                    if 0 <= c1_idx < self.num_cores and 0 <= c2_idx < self.num_cores:
                        self.pheromone[c1_idx][c2_idx] += delta_tau

            delta_best = (2.5 * self.q_value) / float(best_makespan)
            for k in range(len(best_tasks) - 1):
                c1_idx = best_tasks[k].core_id - 1
                c2_idx = best_tasks[k+1].core_id - 1
                if 0 <= c1_idx < self.num_cores and 0 <= c2_idx < self.num_cores:
                    self.pheromone[c1_idx][c2_idx] += delta_best

        return self._generate_schedule_result(best_tasks, best_makespan)

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
            algorithm_name="Modified ACO (MACO 3D)",
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
