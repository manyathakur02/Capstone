"""
src/hardware/rpi_tester.py
==========================
Phase 3: Hardware-in-the-Loop (HIL) Validation for Raspberry Pi 5 Hardware Tester.
Translates optimized 3D test schedules into physical execution sequences:
- Pin mapping for TAM data channels & clock pulses.
- Real-time hardware latency & transmission overhead verification.
- Includes automatic Fallback Simulation Engine for non-Raspberry Pi environments.
"""

import time
import json
import logging
from typing import Dict, List, Optional
from src.models.soc_3d import ScheduleResult3D, ScheduledTask3D

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [RPi-Tester] - %(levelname)s - %(message)s")

# Attempt RPi.GPIO import with graceful mock fallback
try:
    import RPi.GPIO as GPIO
    IS_RPI_HARDWARE = True
except (ImportError, RuntimeError):
    IS_RPI_HARDWARE = False
    GPIO = None


class RaspberryPi5Tester:
    """
    Raspberry Pi 5 Hardware-in-the-Loop (HIL) Interface & Execution Engine.
    """
    def __init__(
        self,
        clock_pin: int = 18,
        tam_control_pins: Optional[List[int]] = None,
        test_clock_freq_hz: float = 1000.0,
        mock_mode: bool = not IS_RPI_HARDWARE
    ):
        self.clock_pin = clock_pin
        self.tam_control_pins = tam_control_pins or [2, 3, 4, 14, 15, 17, 27, 22]
        self.test_clock_freq_hz = test_clock_freq_hz
        self.mock_mode = mock_mode
        self.cycle_time_sec = 1.0 / test_clock_freq_hz

        self.hardware_status = "Initialized (Mock Engine)" if self.mock_mode else "Initialized (Physical RPi 5)"
        logging.info(f"RPi 5 Tester Bridge Status: {self.hardware_status}")
        self._setup_hardware()

    def _setup_hardware(self):
        """Initializes GPIO pins or mock interfaces."""
        if not self.mock_mode and GPIO is not None:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.clock_pin, GPIO.OUT)
                for pin in self.tam_control_pins:
                    GPIO.setup(pin, GPIO.OUT)
                logging.info("Physical RPi 5 GPIO pins initialized successfully.")
            except Exception as e:
                logging.warning(f"GPIO setup failed ({e}). Falling back to Mock Hardware Engine.")
                self.mock_mode = True

    def replay_schedule(self, schedule_result: ScheduleResult3D, time_scale_factor: float = 1e-5) -> Dict[str, any]:
        """
        Executes physical schedule replay of test vectors over TAM channels.
        
        Args:
            schedule_result: ScheduleResult3D object containing task sequences.
            time_scale_factor: Scaling factor to convert simulated test cycles to physical wall-clock time.
            
        Returns:
            Dictionary containing hardware execution logs, measured latency, and transmission overhead.
        """
        logging.info(f"Beginning HIL Schedule Replay for '{schedule_result.algorithm_name}'")
        logging.info(f"Target Schedule Makespan: {schedule_result.makespan:,} cycles")

        start_wall_time = time.perf_counter()
        task_events = []

        # Sort tasks by start time for event-driven hardware triggering
        sorted_tasks = sorted(schedule_result.tasks, key=lambda t: t.start_time)

        total_overhead_sec = 0.0
        cycles_replayed = 0

        for task in sorted_tasks:
            # Physical TAM bus pin assignment based on layer and TAM width
            active_pins = self.tam_control_pins[:min(task.tam_width, len(self.tam_control_pins))]

            # Measure pin configuration overhead lag
            t_pin_start = time.perf_counter()
            self._toggle_tam_pins(active_pins, high=True)
            t_pin_end = time.perf_counter()
            overhead_lag = t_pin_end - t_pin_start
            total_overhead_sec += overhead_lag

            # Simulate clock pulse streaming for core test cycles
            simulated_execution_time = (task.duration * time_scale_factor)
            time.sleep(simulated_execution_time)

            cycles_replayed += task.duration

            # De-assert TAM pins after task completion
            self._toggle_tam_pins(active_pins, high=False)

            task_events.append({
                "core_id": task.core_id,
                "core_name": task.core_name,
                "layer_id": task.layer_id,
                "start_cycle": task.start_time,
                "end_cycle": task.end_time,
                "hardware_pins_used": active_pins,
                "pin_setup_overhead_ms": overhead_lag * 1000.0
            })

        end_wall_time = time.perf_counter()
        total_wall_time = end_wall_time - start_wall_time

        expected_pure_time = schedule_result.makespan * time_scale_factor
        hardware_overhead_percentage = ((total_wall_time - expected_pure_time) / expected_pure_time * 100.0) if expected_pure_time > 0 else 0.0

        performance_report = {
            "algorithm": schedule_result.algorithm_name,
            "hardware_mode": "Physical RPi 5 GPIO" if not self.mock_mode else "Mock RPi 5 Simulator",
            "makespan_cycles": schedule_result.makespan,
            "cycles_replayed": cycles_replayed,
            "total_wall_clock_sec": round(total_wall_time, 4),
            "expected_pure_time_sec": round(expected_pure_time, 4),
            "total_hardware_overhead_sec": round(total_overhead_sec, 6),
            "overhead_percentage": round(hardware_overhead_percentage, 2),
            "peak_power_watts": schedule_result.peak_power,
            "peak_temperature_celsius": schedule_result.peak_temperature,
            "max_tsv_channels_used": schedule_result.max_tsv_used,
            "task_events_count": len(task_events)
        }

        logging.info(f"HIL Replay Completed successfully in {total_wall_time:.4f} seconds.")
        logging.info(f"Hardware Overhead: {hardware_overhead_percentage:.2f}% | Mode: {performance_report['hardware_mode']}")

        return performance_report

    def _toggle_tam_pins(self, pins: List[int], high: bool):
        """Toggles hardware or mock GPIO pins."""
        if not self.mock_mode and GPIO is not None:
            state = GPIO.HIGH if high else GPIO.LOW
            for pin in pins:
                GPIO.output(pin, state)
        else:
            # Mock delay representing microsecond GPIO register write latency
            time.sleep(0.00005 * len(pins))

    def cleanup(self):
        """Cleans up GPIO pins on exit."""
        if not self.mock_mode and GPIO is not None:
            try:
                GPIO.cleanup()
                logging.info("RPi 5 GPIO pins cleaned up.")
            except Exception:
                pass


if __name__ == "__main__":
    from src.models.soc_3d import ITC02BenchmarkLoader
    from src.algorithms.maco_3d import MACO3DScheduler

    soc = ITC02BenchmarkLoader.load_d695_3d()
    maco = MACO3DScheduler(soc, num_ants=15, max_iterations=15)
    res = maco.optimize()

    tester = RaspberryPi5Tester(mock_mode=True)
    report = tester.replay_schedule(res)
    print("\n--- HIL Validation Performance Report ---")
    print(json.dumps(report, indent=2))
