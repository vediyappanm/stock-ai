"""
Performance optimization utilities for faster predictions.
"""
import logging
import time
from functools import wraps
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

# Global thread pool for CPU-bound tasks
_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stk_perf")

def performance_monitor(func_name: str = None):
    """Decorator to monitor function execution time."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000
                
                if duration > 1000:  # Log slow operations (>1s)
                    logger.warning(f"⚠️  SLOW: {name} took {duration:.0f}ms")
                elif duration > 500:  # Log medium operations (>500ms)
                    logger.info(f"🐌 {name} took {duration:.0f}ms")
                else:
                    logger.debug(f"⚡ {name} took {duration:.0f}ms")
                
                return result
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                logger.error(f"❌ {name} failed after {duration:.0f}ms: {e}")
                raise
                
        return wrapper
    return decorator

def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """Run CPU-bound function in thread pool."""
    future = _thread_pool.submit(func, *args, **kwargs)
    return future.result()

async def run_in_thread_async(func: Callable, *args, **kwargs) -> Any:
    """Run CPU-bound function in thread pool asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_thread_pool, func, *args, **kwargs)

def optimize_dataframe_memory(df):
    """Optimize pandas DataFrame memory usage."""
    if df is None or df.empty:
        return df
        
    # Downcast numeric types
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = df[col].astype('int32')
    
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = df[col].astype('float32')
    
    return df

class PerformanceTracker:
    """Track performance metrics across the application."""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation."""
        self.start_times[operation] = time.perf_counter()
    
    def end_timer(self, operation: str) -> float:
        """End timing and return duration in milliseconds."""
        if operation not in self.start_times:
            return 0.0
            
        duration = (time.perf_counter() - self.start_times[operation]) * 1000
        
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(duration)
        del self.start_times[operation]
        
        return duration
    
    def get_stats(self, operation: str = None) -> dict:
        """Get performance statistics."""
        if operation:
            if operation not in self.metrics:
                return {}
            
            times = self.metrics[operation]
            return {
                "count": len(times),
                "avg_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "total_ms": sum(times)
            }
        
        # Return all stats
        return {op: self.get_stats(op) for op in self.metrics.keys()}

# Global performance tracker
perf_tracker = PerformanceTracker()