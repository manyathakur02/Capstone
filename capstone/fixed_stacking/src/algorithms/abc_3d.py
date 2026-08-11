"""
src/algorithms/abc_3d.py
========================
3D-Aware Artificial Bee Colony (ABC) Algorithm for 3D SoC Test Scheduling.
Enforces multi-constraint 3D packing across full task execution intervals.
"""

import random
import numpy as np
from typing import List, Tuple
from src.models.soc_3d import SoC3D, Core3D, ScheduledTask3D, ScheduleResult3D, compute_empirical_constraint_status


class ABC3DScheduler:
    def __init__(
        self,
        soc: SoC3D,
        colony_size: int = 20,
        max_iterations: int = 30,
        limit: int = 8
    ):
        self.soc = soc
        self.colony_size = colony_size
        self.num_employed = colony_size // 2
        self.num_onlookers = colony_size // 2
        self.max_iterations = max_iterations
        self.limit = limit
        self.num_cores = len(soc.cores)

    def _decode_permutation(self, position_vector: np.ndarray) -> List[int]:
        return list(np.argsort(position_vector))

    def _evaluate_schedule(self, order: List[int]) -> Tuple[int, List[ScheduledTask3D]]:
        scheduled_tasks: List[ScheduledTask3D] = []
        completion_events = set([0])

        for core_idx in order:
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
        food_sources = np.random.uniform(0, 1, (self.num_employed, self.num_cores))
        fitness = np.zeros(self.num_employed)
        trial_counts = np.zeros(self.num_employed)

        best_makespan = float('inf')
        best_tasks = []

        for i in range(self.num_employed):
            order = self._decode_permutation(food_sources[i])
            mk, tasks = self._evaluate_schedule(order)
            fitness[i] = 1.0 / float(mk)
            if mk < best_makespan:
                best_makespan = mk
                best_tasks = tasks

        for it in range(self.max_iterations):
            for i in range(self.num_employed):
                k = random.choice([idx for idx in range(self.num_employed) if idx != i])
                phi = np.random.uniform(-1, 1, self.num_cores)
                v = food_sources[i] + phi * (food_sources[i] - food_sources[k])
                v = np.clip(v, 0, 1)

                v_order = self._decode_permutation(v)
                v_mk, v_tasks = self._evaluate_schedule(v_order)
                v_fit = 1.0 / float(v_mk)

                if v_fit > fitness[i]:
                    food_sources[i] = v
                    fitness[i] = v_fit
                    trial_counts[i] = 0
                    if v_mk < best_makespan:
                        best_makespan = v_mk
                        best_tasks = v_tasks
                else:
                    trial_counts[i] += 1

            total_fit = np.sum(fitness)
            probs = fitness / total_fit if total_fit > 0 else np.full(self.num_employed, 1.0/self.num_employed)

            for _ in range(self.num_onlookers):
                i = np.random.choice(range(self.num_employed), p=probs)
                k = random.choice([idx for idx in range(self.num_employed) if idx != i])
                phi = np.random.uniform(-1, 1, self.num_cores)
                v = food_sources[i] + phi * (food_sources[i] - food_sources[k])
                v = np.clip(v, 0, 1)

                v_order = self._decode_permutation(v)
                v_mk, v_tasks = self._evaluate_schedule(v_order)
                v_fit = 1.0 / float(v_mk)

                if v_fit > fitness[i]:
                    food_sources[i] = v
                    fitness[i] = v_fit
                    trial_counts[i] = 0
                    if v_mk < best_makespan:
                        best_makespan = v_mk
                        best_tasks = v_tasks
                else:
                    trial_counts[i] += 1

            for i in range(self.num_employed):
                if trial_counts[i] >= self.limit:
                    food_sources[i] = np.random.uniform(0, 1, self.num_cores)
                    order = self._decode_permutation(food_sources[i])
                    mk, tasks = self._evaluate_schedule(order)
                    fitness[i] = 1.0 / float(mk)
                    trial_counts[i] = 0
                    if mk < best_makespan:
                        best_makespan = mk
                        best_tasks = tasks

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
            algorithm_name="Artificial Bee Colony (ABC 3D)",
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
