"""
src/algorithms/bat_3d.py
========================
3D-Aware Bat Algorithm for 3D SoC Test Scheduling.
Enforces multi-constraint 3D packing across full task execution intervals.
"""

import math
import random
import numpy as np
from typing import List, Tuple
from src.models.soc_3d import SoC3D, Core3D, ScheduledTask3D, ScheduleResult3D, compute_empirical_constraint_status


class Bat3DScheduler:
    def __init__(
        self,
        soc: SoC3D,
        num_bats: int = 20,
        max_iterations: int = 30,
        f_min: float = 0.0,
        f_max: float = 2.0,
        alpha_loudness: float = 0.9,
        gamma_pulse: float = 0.9
    ):
        self.soc = soc
        self.num_bats = num_bats
        self.max_iterations = max_iterations
        self.f_min = f_min
        self.f_max = f_max
        self.alpha_loudness = alpha_loudness
        self.gamma_pulse = gamma_pulse
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
        positions = np.random.uniform(0, 1, (self.num_bats, self.num_cores))
        velocities = np.zeros((self.num_bats, self.num_cores))
        loudness = np.ones(self.num_bats)
        pulse_rate = np.random.uniform(0.1, 0.5, self.num_bats)

        best_makespan = float('inf')
        best_pos = None
        best_tasks = []

        for i in range(self.num_bats):
            order = self._decode_permutation(positions[i])
            makespan, tasks = self._evaluate_schedule(order)
            if makespan < best_makespan:
                best_makespan = makespan
                best_pos = positions[i].copy()
                best_tasks = tasks

        for t in range(self.max_iterations):
            for i in range(self.num_bats):
                beta = random.random()
                freq = self.f_min + (self.f_max - self.f_min) * beta
                velocities[i] = velocities[i] + (positions[i] - best_pos) * freq
                new_pos = positions[i] + velocities[i]

                if random.random() > pulse_rate[i]:
                    new_pos = best_pos + 0.05 * np.random.randn(self.num_cores)

                new_order = self._decode_permutation(new_pos)
                new_makespan, new_tasks = self._evaluate_schedule(new_order)

                if (new_makespan <= best_makespan) and (random.random() < loudness[i]):
                    positions[i] = new_pos
                    loudness[i] *= self.alpha_loudness
                    pulse_rate[i] = pulse_rate[i] * (1.0 - math.exp(-self.gamma_pulse * t))

                if new_makespan < best_makespan:
                    best_makespan = new_makespan
                    best_pos = new_pos.copy()
                    best_tasks = new_tasks

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
            algorithm_name="Bat Algorithm (Bat 3D)",
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
