# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Specification Validator for Monitor Service

Validates DataCollectionSpec for correctness and completeness.
"""

from typing import Dict, Any
from models import DataCollectionSpec

class SpecificationValidator:
    """Validates DataCollectionSpec for correctness and completeness"""
    
    def validate(self, spec: DataCollectionSpec) -> Dict[str, Any]:
        """Validate a specification and return validation result"""
        errors = []
        warnings = []
        
        # Basic validation
        if not spec.spec_id:
            errors.append("spec_id is required")
        
        if spec.request_type not in ["pattern", "investigation"]:
            errors.append("request_type must be 'pattern' or 'investigation'")

        # Schedule validation for pattern requests
        if spec.request_type == "pattern" and spec.schedule:
            if spec.schedule.get('enabled', False) and not spec.schedule.get('interval'):
                errors.append("interval is required when schedule is enabled. {}".format(spec.schedule)) 
        
        # Target validation
        if not spec.target_nodes and not spec.target_jobs:
            errors.append("Either target_nodes or target_jobs must be specified")
        
        # Requirements validation
        if not spec.metrics_requirements and not spec.logs_requirements and not spec.api_requirements:
            errors.append("At least one requirement type must be specified")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        } 