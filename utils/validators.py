# utils/validators.py
"""
Validation utilities for Rake Planning System
"""

from typing import Dict, List, Tuple
from collections import defaultdict
from data.models import RakeType


class Validator:
    """Validates optimization plans against constraints"""

    @staticmethod
    def validate_plan(plan: Dict, rake_type_id: int, rake_config: Dict) -> Dict:
        """
        Validate the optimized plan

        Args:
            plan: Optimization result dictionary
            rake_type_id: Type of rake used
            rake_config: Rake configuration dictionary

        Returns:
            Validation results
        """
        if not plan.get("success"):
            return {"valid": False, "error": plan.get("error", "Invalid plan")}

        wagons_data = plan.get("wagons", [])
        if not wagons_data:
            return {"valid": False, "error": "No wagon data"}

        # Group by wagon
        wagons = defaultdict(list)
        for item in wagons_data:
            wagons[item["WAGON_ID"]].append(item)

        rake = rake_config.get(rake_type_id)
        if not rake:
            return {"valid": False, "error": f"Invalid rake type: {rake_type_id}"}

        rake_obj = RakeType(
            type_id=rake_type_id,
            name=rake['name'],
            min_weight=rake['min_weight'],
            max_weight=rake['max_weight'],
            total_capacity=rake['total_capacity'],
            no_wagons=rake['no_wagons']
        )

        valid_combos = [(1, 2, 0), (2, 1, 0), (0, 3, 0), (4, 0, 0), (0, 0, 2), (1, 1, 1)]

        violations = []
        warnings = []
        total_weight = 0
        valid_count = 0

        for wagon_id, coils in wagons.items():
            wagon_weight = sum(c["STOCK_WEIGHT"] for c in coils)
            total_weight += wagon_weight

            narrow = sum(1 for c in coils if 900 <= c["STOCK_WIDTH"] <= 1199)
            wider = sum(1 for c in coils if 1200 <= c["STOCK_WIDTH"] <= 1499)
            extra = sum(1 for c in coils if 1500 <= c["STOCK_WIDTH"] <= 2000)

            if (narrow, wider, extra) in valid_combos:
                valid_count += 1
            elif narrow + wider + extra > 0:
                warnings.append(f"Wagon {wagon_id}: Invalid combination - N:{narrow} W:{wider} E:{extra}")

            if wagon_weight > rake_obj.max_weight:
                violations.append(f"Wagon {wagon_id}: Weight {wagon_weight:.0f}kg > {rake_obj.max_weight}kg")
            elif wagon_weight < rake_obj.min_weight * 0.8:
                warnings.append(f"Wagon {wagon_id}: Underfilled at {wagon_weight:.0f}kg")

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "total_weight_kg": total_weight,
            "total_wagons": len(wagons),
            "valid_combinations": valid_count,
            "utilization_percent": (total_weight / rake_obj.total_capacity) * 100
        }