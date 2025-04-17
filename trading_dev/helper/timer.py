# helper/timer.py
# Overview:
# This module provides a timing utility for the #SeanProjectTrading system. It defines a single
# decorator, `measure_time`, which measures the execution duration of functions and logs it
# using the `Logging` class from `helper/logging.py`. The decorator is designed to integrate
# with the system's logging framework, writing timing information to the configured log file
# at DEBUG level, with a fallback to console output if no logger is provided.
#
# Purpose:
# - To profile the performance of key functions (e.g., data analysis, trading simulations).
# - To assist in debugging and optimization by tracking execution times during logger runs.
#
# Usage:
# - Import: `from helper.timer import measure_time`
# - Apply: Decorate functions with `@measure_time` and pass a `Logging` instance via the `logger`
#   keyword argument.
# - Example:
#   ```python
#   from helper.config_manager import ConfigManager
#   from helper.logging import Logging
#   from helper.timer import measure_time
#
#   @measure_time
#   def my_task(logger=None):
#       time.sleep(1)
#       if logger:
#           logger.info("Task complete")
#
#   config = ConfigManager()
#   logger = Logging()
#   my_task(logger=logger)  # Logs: "Function 'my_task' took 1.001 seconds"
#   ```
#
# Dependencies:
# - `time`: For high-precision timing.
# - `functools.wraps`: To preserve the wrapped function's metadata.
#
# Ideas:
# 1. timer-1: Add an optional threshold parameter to log only if duration exceeds a limit.
# 2. timer-2: Extend to log start/end timestamps alongside duration for detailed tracing.
# 3. timer-3: Support multiple timing runs and average reporting for repeated calls.
#
# Warnings:
# 1. timer-1: Console fallback might clutter output in production if logger isn’t provided.
# 2. timer-2: Precision of `time.time()` may vary slightly across platforms.
#
# Cautions:
# 1. timer-1: Overhead from decorator might skew timings for very short functions.
# 2. timer-2: Logger dependency assumes `Logging` is initialized; uncaught errors could silent fail.
#
# Future Enhancements:
# 1. timer-1: Use `time.perf_counter()` for even higher precision in timing.
# 2. timer-2: Integrate with a profiling tool (e.g., `cProfile`) for deeper analysis.
# 3. timer-3: Add timing stats aggregation (e.g., min/max/avg) across function calls.

# helper/timer.py
# helper/timer.py
import time
from functools import wraps
import asyncio

def measure_time(func):
    """Decorator to measure and log the execution time of a function, supporting both sync and async."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = kwargs.pop('logger', None)  # Remove logger from kwargs
        start = time.perf_counter()
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        end = time.perf_counter()
        duration = end - start
        if logger:
            logger.debug(f"Function '{func.__name__}' took {duration:.3f} seconds")
        return result
    if asyncio.iscoroutinefunction(func):
        return wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = kwargs.pop('logger', None)  # Remove logger from kwargs
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            duration = end - start
            if logger:
                logger.debug(f"Function '{func.__name__}' took {duration:.3f} seconds")
            return result
        return sync_wrapper