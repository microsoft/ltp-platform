import importlib
import importlib.util
import pkgutil
import os
import sys
import logging
from typing import Callable, Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Support both built-in patterns and ConfigMap-mounted patterns
DEFAULT_PATTERNS_PATH = os.path.join(os.path.dirname(__file__), 'patterns')
PATTERNS_PATH = os.getenv('PATTERNS_DIR', DEFAULT_PATTERNS_PATH)
PATTERNS_PACKAGE = __name__.replace('pattern_registry', 'patterns')

class PatternRegistry:
    """
    Unified pattern registry that handles both pattern discovery/loading 
    and runtime storage/access of patterns.
    """
    
    def __init__(self):
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self.loaded_modules: List[str] = []
        self.patterns_package = PATTERNS_PACKAGE
        self.patterns_path = PATTERNS_PATH

    def register_pattern(self, pattern_id: str, description: str, required_data: list, 
                        analysis_method: Callable, schedule: Optional[str], data_spec: dict):
        """Register a pattern with the registry"""
        self._patterns[pattern_id] = {
            'pattern_id': pattern_id,
            'description': description,
            'required_data': required_data,
            'analysis_method': analysis_method,
            'schedule': schedule,
            'data_spec': data_spec
        }
        logger.debug(f"Registered pattern: {pattern_id}")

    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific pattern by ID"""
        return self._patterns.get(pattern_id)

    def list_patterns(self) -> List[Dict[str, Any]]:
        """List all registered patterns"""
        return list(self._patterns.values())
    
    def load_all_patterns(self) -> List[str]:
        """
        Import all pattern modules from the patterns directory to trigger their registration.
        Supports both package-based loading (built-in) and file-based loading (ConfigMap).
        
        Returns:
            List of successfully loaded pattern module names
        """
        logger.info(f"Loading patterns from {self.patterns_path}")
        loaded = []
        
        if not os.path.exists(self.patterns_path):
            logger.warning(f"Patterns directory not found: {self.patterns_path}")
            return loaded
        
        # Check if this is a ConfigMap-mounted directory (contains .py files directly)
        is_configmap_mount = self._is_configmap_patterns_dir()
        
        if is_configmap_mount:
            logger.info("Detected ConfigMap-mounted patterns directory")
            loaded = self._load_patterns_from_files()
        else:
            logger.info("Using package-based pattern loading")
            loaded = self._load_patterns_from_package()
        
        self.loaded_modules = loaded
        logger.info(f"Pattern loading complete. Loaded {len(loaded)} patterns: {loaded}")
        return loaded
    
    def _is_configmap_patterns_dir(self) -> bool:
        """Check if patterns directory contains .py files (ConfigMap mount) vs packages"""
        patterns_path = Path(self.patterns_path)
        py_files = list(patterns_path.glob("*.py"))
        return len(py_files) > 0 and not (patterns_path / "__init__.py").exists()
    
    def _load_patterns_from_files(self) -> List[str]:
        """Load patterns from individual .py files (ConfigMap mount)"""
        loaded = []
        patterns_path = Path(self.patterns_path)
        
        # Add patterns directory to Python path
        if str(patterns_path) not in sys.path:
            sys.path.insert(0, str(patterns_path))
        
        for py_file in patterns_path.glob("*.py"):
            module_name = py_file.stem
            
            # Skip private modules and template
            if module_name.startswith('_') or module_name == 'pattern_template':
                continue
                
            if self._load_pattern_module_from_file(str(py_file), module_name):
                loaded.append(module_name)
                
        return loaded
    
    def _load_patterns_from_package(self) -> List[str]:
        """Load patterns from Python package (built-in patterns)"""
        loaded = []
        
        for _, module_name, is_pkg in pkgutil.iter_modules([self.patterns_path]):
            # Skip packages, private modules, and template
            if is_pkg or module_name.startswith('_') or module_name == 'pattern_template':
                continue
                
            if self._load_pattern_module(module_name):
                loaded.append(module_name)
                
        return loaded
    
    def _load_pattern_module_from_file(self, file_path: str, module_name: str) -> bool:
        """Load a pattern module from a specific file path"""
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Add to sys.modules so it can be imported later
                sys.modules[module_name] = module
                
                logger.debug(f"Successfully loaded pattern module from file: {module_name}")
                return True
            else:
                logger.error(f"Could not create module spec for {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading pattern module {module_name} from {file_path}: {e}")
            return False
    
    def reload_pattern(self, module_name: str) -> bool:
        """
        Reload a specific pattern module.
        
        Args:
            module_name: Name of the pattern module to reload
            
        Returns:
            True if reload was successful, False otherwise
        """
        try:
            module_path = f"{self.patterns_package}.{module_name}"
            
            # Check if module is already loaded
            if module_path in importlib.sys.modules:
                logger.info(f"Reloading pattern module: {module_name}")
                importlib.reload(importlib.sys.modules[module_path])
            else:
                logger.info(f"Loading pattern module: {module_name}")
                importlib.import_module(module_path)
            
            if module_name not in self.loaded_modules:
                self.loaded_modules.append(module_name)
            
            logger.info(f"Successfully reloaded pattern module: {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload pattern module {module_name}: {e}")
            return False
    
    def _load_pattern_module(self, module_name: str) -> bool:
        """Load a single pattern module"""
        try:
            module_path = f"{self.patterns_package}.{module_name}"
            logger.debug(f"Loading pattern module: {module_path}")
            
            # Import the module (this triggers pattern registration via class instantiation)
            importlib.import_module(module_path)
            
            logger.info(f"Successfully loaded pattern module: {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load pattern module {module_name}: {e}")
            return False
    
    def get_loaded_modules(self) -> List[str]:
        """Get list of successfully loaded pattern module names"""
        return self.loaded_modules.copy()
    
    def validate_patterns_directory(self) -> bool:
        """Check if patterns directory exists and is accessible"""
        if not os.path.exists(self.patterns_path):
            logger.error(f"Patterns directory does not exist: {self.patterns_path}")
            return False
        
        if not os.path.isdir(self.patterns_path):
            logger.error(f"Patterns path is not a directory: {self.patterns_path}")
            return False
        
        # Check if directory is readable
        try:
            os.listdir(self.patterns_path)
            return True
        except PermissionError:
            logger.error(f"No permission to read patterns directory: {self.patterns_path}")
            return False
    
    def list_available_pattern_files(self) -> List[str]:
        """List all available pattern files in the patterns directory"""
        if not self.validate_patterns_directory():
            return []
        
        pattern_files = []
        for _, module_name, is_pkg in pkgutil.iter_modules([self.patterns_path]):
            if not is_pkg and not module_name.startswith('_') and module_name != 'pattern_template':
                pattern_files.append(module_name)
        
        return pattern_files
    
    def clear_patterns(self):
        """Clear all registered patterns (useful for testing)"""
        self._patterns.clear()
        self.loaded_modules.clear()
        logger.info("Cleared all patterns from registry")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the pattern registry"""
        patterns = self.list_patterns()
        return {
            "total_patterns": len(patterns),
            "scheduled_patterns": len([p for p in patterns if p.get('schedule')]),
            "event_driven_patterns": len([p for p in patterns if not p.get('schedule')]),
            "loaded_modules": self.get_loaded_modules(),
            "available_files": self.list_available_pattern_files(),
            "patterns_directory": self.patterns_path,
            "patterns_directory_valid": self.validate_patterns_directory(),
            "patterns": [
                {
                    "pattern_id": p['pattern_id'],
                    "description": p['description'],
                    "schedule": p.get('schedule', 'event-driven'),
                    "required_data": p.get('required_data', [])
                }
                for p in patterns
            ]
        }

# Global registry instance
pattern_registry = PatternRegistry()

def register_pattern(pattern_id: str, description: str, required_data: list, 
                    analysis_method: Callable, schedule: Optional[str], data_spec: dict):
    """Global function to register a pattern with the default registry"""
    pattern_registry.register_pattern(pattern_id, description, required_data, analysis_method, schedule, data_spec)

