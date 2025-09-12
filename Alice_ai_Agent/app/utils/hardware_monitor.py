import psutil
import asyncio
import logging
from typing import Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class HardwareStats:
    """Hardware statistics container."""
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    cpu_cores: int
    load_average: Tuple[float, float, float]
    recommended_workers: int
    performance_level: str

class HardwareMonitor:
    """Monitor system resources and provide optimal parallel processing recommendations."""
    
    def __init__(self):
        self.cpu_cores = psutil.cpu_count(logical=True)
        self.total_memory = psutil.virtual_memory().total / (1024**3)  # GB
        logger.info(f"Hardware monitor initialized - Cores: {self.cpu_cores}, Memory: {self.total_memory:.1f}GB")
    
    async def get_system_stats(self) -> HardwareStats:
        """Get current system resource utilization."""
        try:
            # Get CPU usage (averaged over 1 second for accuracy)
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Get load average (Linux/macOS) or simulate for Windows
            try:
                load_average = psutil.getloadavg()
            except AttributeError:
                # Windows doesn't have load average, simulate it
                load_average = (cpu_percent/100, cpu_percent/100, cpu_percent/100)
            
            # Calculate optimal worker count based on resources
            recommended_workers = self._calculate_optimal_workers(cpu_percent, memory_percent)
            
            # Assess overall performance level
            performance_level = self._assess_performance_level(cpu_percent, memory_percent)
            
            return HardwareStats(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                cpu_cores=self.cpu_cores,
                load_average=load_average,
                recommended_workers=recommended_workers,
                performance_level=performance_level
            )
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            # Return conservative defaults
            return HardwareStats(
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_available_gb=1.0,
                cpu_cores=self.cpu_cores,
                load_average=(1.0, 1.0, 1.0),
                recommended_workers=2,
                performance_level="moderate"
            )
    
    def _calculate_optimal_workers(self, cpu_percent: float, memory_percent: float) -> int:
        """Calculate optimal number of parallel workers based on current system load."""
        base_workers = max(2, self.cpu_cores - 1)  # Leave one core free
        
        # Reduce workers based on current load
        if cpu_percent > 80 or memory_percent > 85:
            workers = max(1, base_workers // 3)
        elif cpu_percent > 60 or memory_percent > 70:
            workers = max(2, base_workers // 2)
        elif cpu_percent > 40 or memory_percent > 50:
            workers = max(2, int(base_workers * 0.75))
        else:
            workers = base_workers
        
        # Cap based on available memory (assume ~200MB per worker)
        memory_gb = psutil.virtual_memory().available / (1024**3)
        memory_based_limit = max(1, int(memory_gb * 5))  # 5 workers per GB available
        
        optimal_workers = min(workers, memory_based_limit, 10)  # Cap at 10 workers max
        
        logger.debug(f"Calculated optimal workers: {optimal_workers} (CPU: {cpu_percent}%, Memory: {memory_percent}%)")
        return optimal_workers
    
    def _assess_performance_level(self, cpu_percent: float, memory_percent: float) -> str:
        """Assess current system performance level."""
        if cpu_percent > 85 or memory_percent > 90:
            return "critical"
        elif cpu_percent > 70 or memory_percent > 75:
            return "high"
        elif cpu_percent > 50 or memory_percent > 60:
            return "moderate"
        else:
            return "optimal"
    
    async def get_performance_recommendations(self) -> Dict[str, str]:
        """Get recommendations for optimal performance."""
        stats = await self.get_system_stats()
        
        recommendations = {}
        
        if stats.performance_level == "critical":
            recommendations["status"] = "System under heavy load"
            recommendations["action"] = "Reduce concurrent operations, consider waiting"
            recommendations["workers"] = f"Using minimal workers: {stats.recommended_workers}"
        elif stats.performance_level == "high":
            recommendations["status"] = "System moderately loaded"
            recommendations["action"] = "Proceeding with reduced parallelism"
            recommendations["workers"] = f"Using conservative workers: {stats.recommended_workers}"
        elif stats.performance_level == "moderate":
            recommendations["status"] = "System performing well"
            recommendations["action"] = "Normal operation with balanced parallelism"
            recommendations["workers"] = f"Using optimal workers: {stats.recommended_workers}"
        else:
            recommendations["status"] = "System resources available"
            recommendations["action"] = "Can use maximum parallelism for best performance"
            recommendations["workers"] = f"Using full workers: {stats.recommended_workers}"
        
        return recommendations
    
    async def wait_for_resources(self, required_memory_gb: float = 0.5, max_cpu_percent: float = 80) -> bool:
        """Wait for system resources to become available."""
        max_wait_time = 30  # Maximum 30 seconds
        wait_interval = 2   # Check every 2 seconds
        waited = 0
        
        while waited < max_wait_time:
            stats = await self.get_system_stats()
            
            if (stats.cpu_percent <= max_cpu_percent and 
                stats.memory_available_gb >= required_memory_gb):
                logger.info(f"Resources available after waiting {waited}s")
                return True
            
            logger.debug(f"Waiting for resources... CPU: {stats.cpu_percent}%, "
                        f"Memory: {stats.memory_available_gb:.1f}GB")
            
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        logger.warning(f"Resource wait timeout after {max_wait_time}s")
        return False
    
    def get_hardware_info(self) -> Dict[str, any]:
        """Get static hardware information."""
        try:
            return {
                "cpu_cores_physical": psutil.cpu_count(logical=False),
                "cpu_cores_logical": psutil.cpu_count(logical=True),
                "total_memory_gb": round(self.total_memory, 2),
                "cpu_frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "boot_time": psutil.boot_time(),
                "architecture": psutil.WINDOWS if hasattr(psutil, 'WINDOWS') else "unix"
            }
        except Exception as e:
            logger.error(f"Error getting hardware info: {e}")
            return {"cpu_cores": self.cpu_cores, "total_memory_gb": self.total_memory}