# optimizers/rake_optimizer.py
"""
Core optimization logic for rake planning
"""

from typing import List, Dict
from collections import defaultdict
from data.models import Coil, RakeType, Wagon


class RakeOptimizer:
    """Optimizes loading of coils into wagons"""

    def __init__(self, config, valid_combinations: List[tuple]):
        """
        Initialize optimizer

        Args:
            config: Configuration manager instance
            valid_combinations: List of valid width combinations
        """
        self.config = config
        self.valid_combinations = valid_combinations
        self.max_coils_per_wagon = config.get_max_coils_per_wagon()

    def optimize(self, materials: List[Dict], rake_type_id: int) -> Dict:
        """
        Optimize loading of coils into wagons

        Args:
            materials: List of material dictionaries
            rake_type_id: Type of rake (1=Concord, 2=Jumbo)

        Returns:
            Optimization result with wagons and metrics
        """
        try:
            if not materials:
                return {"success": False, "error": "No materials provided"}

            # Get rake configuration
            rake_config = self.config.get_rake_type(rake_type_id)
            if not rake_config:
                return {"success": False, "error": f"Invalid rake type: {rake_type_id}"}

            rake = RakeType(
                type_id=rake_type_id,
                name=rake_config['name'],
                min_weight=rake_config['min_weight'],
                max_weight=rake_config['max_weight'],
                total_capacity=rake_config['total_capacity'],
                no_wagons=rake_config['no_wagons']
            )

            print(f"\nOptimizing with {rake.name}:")
            print(f"  Max weight per wagon: {rake.max_weight:,} kg")
            print(f"  Total capacity: {rake.total_capacity:,} kg")
            print(f"  Max wagons: {rake.no_wagons}")

            # Create coil objects
            coils = self._create_coils(materials)

            if not coils:
                return {"success": False, "error": "No valid coils found"}

            print(f"Processed {len(coils)} valid coils")

            # Group by location and optimize
            location_groups = defaultdict(list)
            for coil in coils:
                location_groups[coil.location].append(coil)

            print(f"Location groups: {list(location_groups.keys())}")
            for loc, coils_list in location_groups.items():
                print(f"  {loc}: {len(coils_list)} coils")

            all_wagons = self._optimize_by_location(location_groups, rake)

            # Generate output
            output = self._generate_output(all_wagons, rake_type_id)

            # Calculate metrics
            metrics = self._calculate_metrics(all_wagons, coils, rake)

            return {
                "success": True,
                "wagons": output,
                "metrics": metrics
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_coils(self, materials: List[Dict]) -> List[Coil]:
        """Create coil objects from material data"""
        coils = []
        for mat in materials:
            try:
                weight = float(mat.get('STOCK_WEIGHT', 0))
                width = float(mat.get('STOCK_WIDTH', 0))
                if weight > 0 and width > 0:
                    coil = Coil(
                        batch_number=str(mat.get('BATCH_NUMBER', '')),
                        order_number=str(mat.get('ORDER_NUMBER', '')),
                        order_line=str(mat.get('ORDER_LINE_NUMBER', '')),
                        stock_weight=weight,
                        stock_width=width,
                        stock_length=float(mat.get('STOCK_LENGTH', 0)),
                        location=str(mat.get('LOCATION', 'Unknown')).strip()
                    )
                    coils.append(coil)
            except Exception as e:
                continue
        return coils

    def _optimize_by_location(self, location_groups: Dict, rake: RakeType) -> List[Wagon]:
        """Optimize loading by location"""
        all_wagons = []
        wagon_id = 1

        for location, location_coils in location_groups.items():
            print(f"\nProcessing location {location}: {len(location_coils)} coils")

            # Sort by weight (heavy first for better packing)
            location_coils.sort(key=lambda x: x.stock_weight, reverse=True)

            wagons = []

            for coil in location_coils:
                placed = False
                for wagon in wagons:
                    if wagon.add_coil(coil, rake, self.max_coils_per_wagon):
                        placed = True
                        break

                if not placed:
                    new_wagon = Wagon(id=wagon_id, location=location)
                    new_wagon.add_coil(coil, rake, self.max_coils_per_wagon)
                    wagons.append(new_wagon)
                    wagon_id += 1

            all_wagons.extend(wagons)
            print(f"  Created {len(wagons)} wagons for location {location}")

        return all_wagons

    def _generate_output(self, all_wagons: List[Wagon], rake_type_id: int) -> List[Dict]:
        """Generate output dictionary from wagons"""
        output = []
        for wagon in all_wagons:
            for coil in wagon.coils:
                output.append({
                    "GROUP_ID": 1,
                    "BATCH_NUMBER": coil.batch_number,
                    "ORDER_NUMBER": coil.order_number,
                    "ORDER_LINE_NUMBER": coil.order_line,
                    "STOCK_WEIGHT": coil.stock_weight,
                    "STOCK_WIDTH": coil.stock_width,
                    "STOCK_LENGTH": coil.stock_length,
                    "LOCATION": coil.location,
                    "RAKE_TYPE_ID": rake_type_id,
                    "WAGON_ID": wagon.id
                })
        return output

    def _calculate_metrics(self, all_wagons: List[Wagon], coils: List[Coil], rake: RakeType) -> Dict:
        """Calculate optimization metrics"""
        total_weight = sum(w.total_weight for w in all_wagons)

        # Count valid combinations using the stored combinations
        valid_combinations = 0
        for wagon in all_wagons:
            n, w, e = wagon.narrow_count, wagon.wider_count, wagon.extra_count
            if (n, w, e) in self.valid_combinations:
                valid_combinations += 1

        metrics = {
            "total_coils": len(coils),
            "total_wagons": len(all_wagons),
            "total_weight_kg": total_weight,
            "total_weight_tons": total_weight / 1000,
            "capacity_utilization_percent": (total_weight / rake.total_capacity) * 100,
            "valid_combinations_percent": (valid_combinations / len(all_wagons)) * 100 if all_wagons else 0,
            "rake_type": rake.name,
            "max_wagons_allowed": rake.no_wagons,
            "average_wagon_weight": total_weight / len(all_wagons) if all_wagons else 0,
            "target_wagon_weight": rake.get_target_weight()
        }

        return metrics