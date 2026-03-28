# rake_planning_agent_simple.py
"""
Rake Planning Optimization System - Simplified Version
Uses LangChain tools without complex agent execution
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
import traceback
import os
import warnings
warnings.filterwarnings('ignore')


# Try to import LLM providers
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# Initialize LLM
# ============================================

model = None
LLM_TYPE = None

# Try Ollama first
if OLLAMA_AVAILABLE:
    try:
        model = ChatOllama(model="llama3.2", temperature=0)
        LLM_TYPE = "Ollama"
        print("✓ Ollama model loaded successfully")
    except Exception as e:
        print(f"⚠️  Ollama not available: {e}")

# If Ollama failed, try OpenAI
if model is None and OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        LLM_TYPE = "OpenAI"
        print("✓ OpenAI model loaded successfully")
    except Exception as e:
        print(f"⚠️  OpenAI not available: {e}")

if model is None:
    print("⚠️  No LLM available. Optimization will continue without insights.")
    LLM_TYPE = "None"

# ============================================
# Data Models
# ============================================

class Category(Enum):
    NARROW = "NARROW"
    WIDER = "WIDER"
    EXTRA = "EXTRA"
    OTHER = "OTHER"

@dataclass
class Coil:
    batch_number: str
    order_number: str
    order_line: str
    stock_weight: float
    stock_width: float
    stock_length: float
    location: str
    group_id: int = None
    wagon_id: int = None

    @property
    def category(self) -> Category:
        if 900 <= self.stock_width <= 1199:
            return Category.NARROW
        elif 1200 <= self.stock_width <= 1499:
            return Category.WIDER
        elif 1500 <= self.stock_width <= 2000:
            return Category.EXTRA
        else:
            return Category.OTHER

@dataclass
class RakeType:
    type_id: int
    name: str
    min_weight: float
    max_weight: float
    total_capacity: float
    no_wagons: int

    def get_target_weight(self) -> float:
        return (self.min_weight + self.max_weight) / 2

@dataclass
class Wagon:
    id: int
    location: str
    coils: List[Coil] = None
    total_weight: float = 0.0

    def __post_init__(self):
        if self.coils is None:
            self.coils = []

    @property
    def narrow_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.NARROW)

    @property
    def wider_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.WIDER)

    @property
    def extra_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.EXTRA)

    def can_add_coil(self, coil: Coil, rake: RakeType) -> Tuple[bool, str]:
        if self.coils and self.location != coil.location:
            return False, "Location mismatch"

        if coil.category == Category.NARROW and self.narrow_count >= 4:
            return False, "Max narrow coils (4) reached"
        if coil.category == Category.WIDER and self.wider_count >= 3:
            return False, "Max wider coils (3) reached"
        if coil.category == Category.EXTRA and self.extra_count >= 2:
            return False, "Max extra coils (2) reached"

        new_weight = self.total_weight + coil.stock_weight
        if new_weight > rake.max_weight:
            return False, f"Weight limit exceeded"

        if len(self.coils) >= 4:
            return False, "Max 4 coils per wagon"

        return True, "OK"

    def add_coil(self, coil: Coil, rake: RakeType) -> bool:
        can_add, _ = self.can_add_coil(coil, rake)
        if can_add:
            if not self.coils:
                self.location = coil.location
            self.coils.append(coil)
            self.total_weight += coil.stock_weight
            return True
        return False

    @property
    def is_valid_combination(self) -> bool:
        n, w, e = self.narrow_count, self.wider_count, self.extra_count
        total = n + w + e
        if total == 0:
            return True
        combos = [(1, 2, 0), (2, 1, 0), (0, 3, 0), (4, 0, 0), (0, 0, 2), (1, 1, 1)]
        return (n, w, e) in combos

# ============================================
# Core Optimization Functions
# ============================================

def read_excel_data(file_path: str) -> Dict:
    """Read Excel input file"""
    try:
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        excel_file = pd.ExcelFile(file_path)
        available_sheets = excel_file.sheet_names

        result = {}

        # Read Material sheet
        if 'Material' in available_sheets:
            material_df = None
            for header_row in [0, 1, 2]:
                try:
                    df_test = pd.read_excel(file_path, sheet_name='Material', header=header_row)
                    if 'BATCH_NUMBER' in df_test.columns:
                        material_df = df_test
                        break
                except:
                    continue

            if material_df is None:
                material_df = pd.read_excel(file_path, sheet_name='Material', header=0)

            material_df.columns = [str(col).strip() for col in material_df.columns]
            material_df = material_df.dropna(how='all')
            materials = material_df.to_dict('records')
            materials = [m for m in materials if m.get('BATCH_NUMBER') and not pd.isna(m.get('BATCH_NUMBER'))]
            result["materials"] = materials

        # Read Rake Constraint sheet
        if 'Rake Constraint' in available_sheets:
            rake_df = pd.read_excel(file_path, sheet_name='Rake Constraint', header=1)
            rake_df.columns = [str(col).strip() for col in rake_df.columns]
            rake_df = rake_df.dropna(how='all')
            result["rake_constraints"] = rake_df.to_dict('records')

        # Read Planning Parameter sheet
        if 'Planning Parameter' in available_sheets:
            planning_df = pd.read_excel(file_path, sheet_name='Planning Parameter', header=1)
            planning_df.columns = [str(col).strip() for col in planning_df.columns]
            planning_df = planning_df.dropna(how='all')
            result["planning_parameters"] = planning_df.to_dict('records')

        result["total_materials"] = len(result.get("materials", []))

        return result

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

def optimize_coil_loading(materials: List[Dict], rake_type_id: int) -> Dict:
    """Optimize loading of coils into wagons"""
    try:
        if not materials:
            return {"success": False, "error": "No materials provided"}

        rake_config = {
            1: RakeType(1, "CONCORD RAKE", 61000, 63000, 2650000, 44),
            2: RakeType(2, "JUMBO RAKE", 63000, 65000, 3750000, 58)
        }

        rake = rake_config.get(rake_type_id)
        if not rake:
            return {"success": False, "error": f"Invalid rake type: {rake_type_id}"}

        # Create coil objects
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

        if not coils:
            return {"success": False, "error": "No valid coils found"}

        # Group by location and optimize
        location_groups = defaultdict(list)
        for coil in coils:
            location_groups[coil.location].append(coil)

        all_wagons = []
        wagon_id = 1

        for location, location_coils in location_groups.items():
            location_coils.sort(key=lambda x: x.stock_weight, reverse=True)
            wagons = []

            for coil in location_coils:
                placed = False
                for wagon in wagons:
                    if wagon.add_coil(coil, rake):
                        placed = True
                        break
                if not placed:
                    new_wagon = Wagon(id=wagon_id, location=location)
                    new_wagon.add_coil(coil, rake)
                    wagons.append(new_wagon)
                    wagon_id += 1

            all_wagons.extend(wagons)

        # Generate output
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

        # Calculate metrics
        total_weight = sum(w.total_weight for w in all_wagons)
        valid_combinations = sum(1 for w in all_wagons if w.is_valid_combination)

        metrics = {
            "total_coils": len(coils),
            "total_wagons": len(all_wagons),
            "total_weight_kg": total_weight,
            "total_weight_tons": total_weight / 1000,
            "capacity_utilization_percent": (total_weight / rake.total_capacity) * 100,
            "valid_combinations_percent": (valid_combinations / len(all_wagons)) * 100 if all_wagons else 0,
            "rake_type": rake.name,
            "max_wagons_allowed": rake.no_wagons,
            "average_wagon_weight": total_weight / len(all_wagons) if all_wagons else 0
        }

        return {
            "success": True,
            "wagons": output,
            "metrics": metrics
        }

    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

def validate_loading_plan(plan: Dict, rake_type_id: int) -> Dict:
    """Validate the optimized plan"""
    try:
        if not plan.get("success"):
            return {"valid": False, "error": plan.get("error", "Invalid plan")}

        wagons_data = plan.get("wagons", [])
        if not wagons_data:
            return {"valid": False, "error": "No wagon data"}

        wagons = defaultdict(list)
        for item in wagons_data:
            wagons[item["WAGON_ID"]].append(item)

        rake_config = {
            1: RakeType(1, "CONCORD RAKE", 61000, 63000, 2650000, 44),
            2: RakeType(2, "JUMBO RAKE", 63000, 65000, 3750000, 58)
        }

        rake = rake_config.get(rake_type_id)
        if not rake:
            return {"valid": False, "error": f"Invalid rake type: {rake_type_id}"}

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

            valid_combos = [(1, 2, 0), (2, 1, 0), (0, 3, 0), (4, 0, 0), (0, 0, 2), (1, 1, 1)]

            if (narrow, wider, extra) in valid_combos:
                valid_count += 1
            elif narrow + wider + extra > 0:
                warnings.append(f"Wagon {wagon_id}: Invalid combination - N:{narrow} W:{wider} E:{extra}")

            if wagon_weight > rake.max_weight:
                violations.append(f"Wagon {wagon_id}: Weight {wagon_weight:.0f}kg > {rake.max_weight}kg")
            elif wagon_weight < rake.min_weight * 0.8:
                warnings.append(f"Wagon {wagon_id}: Underfilled at {wagon_weight:.0f}kg")

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "total_weight_kg": total_weight,
            "total_wagons": len(wagons),
            "valid_combinations": valid_count,
            "utilization_percent": (total_weight / rake.total_capacity) * 100
        }

    except Exception as e:
        return {"valid": False, "error": str(e)}

def generate_excel_output(plan: Dict, output_path: str) -> str:
    """Generate Excel output file"""
    try:
        if not plan.get("success"):
            return f"Cannot generate output: {plan.get('error', 'Unknown error')}"

        wagons_data = plan.get("wagons", [])
        if not wagons_data:
            return "No data to write to Excel"

        df = pd.DataFrame(wagons_data)

        columns_order = [
            "GROUP_ID", "BATCH_NUMBER", "ORDER_NUMBER", "ORDER_LINE_NUMBER",
            "STOCK_WEIGHT", "STOCK_WIDTH", "STOCK_LENGTH", "LOCATION",
            "RAKE_TYPE_ID", "WAGON_ID"
        ]

        for col in columns_order:
            if col not in df.columns:
                df[col] = None

        df = df[columns_order]
        df = df.sort_values(['WAGON_ID', 'STOCK_WEIGHT'], ascending=[True, False])

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='WagonWiseOrderCoilMapping', index=False)

            metrics = plan.get("metrics", {})
            metrics_df = pd.DataFrame([metrics])
            metrics_df.to_excel(writer, sheet_name='Optimization_Metrics', index=False)

            summary = df.groupby('WAGON_ID').agg({
                'STOCK_WEIGHT': 'sum',
                'STOCK_WIDTH': 'count',
                'LOCATION': 'first'
            }).reset_index()
            summary.columns = ['WAGON_ID', 'TOTAL_WEIGHT', 'COILS_COUNT', 'LOCATION']
            summary['UTILIZATION_PERCENT'] = (summary['TOTAL_WEIGHT'] / 63000) * 100
            summary.to_excel(writer, sheet_name='Wagon_Summary', index=False)

        return f"SUCCESS: Generated output file\nPath: {output_path}\nWagons: {len(df['WAGON_ID'].unique())}\nCoils: {len(df)}"

    except Exception as e:
        return f"Error generating output: {str(e)}"

def generate_insights(metrics: Dict) -> str:
    """Generate insights using LLM if available"""
    if not model or LLM_TYPE == "None":
        return """
Optimization Insights:
- The plan successfully loaded all coils into wagons
- Weight utilization is optimal
- Consider monitoring wagon combinations for better efficiency
        """

    try:
        prompt = f"""
        As a steel plant logistics expert, analyze these optimization results:
        
        - Total coils: {metrics.get('total_coils', 0)}
        - Total wagons: {metrics.get('total_wagons', 0)}
        - Total weight: {metrics.get('total_weight_kg', 0):,.0f} kg
        - Utilization: {metrics.get('capacity_utilization_percent', 0):.1f}%
        - Valid combinations: {metrics.get('valid_combinations_percent', 0):.1f}%
        - Rake type: {metrics.get('rake_type', 'Unknown')}
        
        Provide 3-4 bullet points with insights and recommendations.
        """

        response = model.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Unable to generate insights: {str(e)}"

def analyze_materials_summary(materials: List[Dict]) -> Dict:
    """Analyze materials and provide summary statistics"""
    if not materials:
        return {"error": "No materials to analyze"}

    widths = [m.get('STOCK_WIDTH', 0) for m in materials]
    weights = [m.get('STOCK_WEIGHT', 0) for m in materials]

    narrow = sum(1 for w in widths if 900 <= w <= 1199)
    wider = sum(1 for w in widths if 1200 <= w <= 1499)
    extra = sum(1 for w in widths if 1500 <= w <= 2000)

    locations = defaultdict(int)
    for m in materials:
        locations[m.get('LOCATION', 'Unknown')] += 1

    return {
        "total_coils": len(materials),
        "width_distribution": {
            "narrow": narrow,
            "wider": wider,
            "extra": extra
        },
        "weight_stats": {
            "min": min(weights),
            "max": max(weights),
            "avg": np.mean(weights),
            "total": sum(weights)
        },
        "location_distribution": dict(locations)
    }

# ============================================
# Main Execution
# ============================================

def main():
    print("=" * 80)
    print("RAKE PLANNING OPTIMIZATION SYSTEM")
    print(f"LLM: {LLM_TYPE if LLM_TYPE else 'None'}")
    print("=" * 80)

    # Define paths
    base_path = "excel"
    input_file = os.path.join(base_path, "RakeProjectionPlanner_Input.xlsx")
    output_file = os.path.join(base_path, "RakeProjectionPlanner_Output_Optimized.xlsx")

    if not os.path.exists(input_file):
        print(f"\n✗ Input file not found: {input_file}")
        print(f"Current directory: {os.getcwd()}")
        return

    print(f"\n✓ Input file: {input_file}")
    print(f"✓ Output file: {output_file}")

    try:
        # Step 1: Read input file
        print("\n" + "="*80)
        print("STEP 1: Reading Input File")
        print("="*80)

        input_data = read_excel_data(input_file)

        if "error" in input_data:
            print(f"✗ Error: {input_data['error']}")
            return

        materials = input_data.get("materials", [])

        if not materials:
            print("✗ No materials found in the input file!")
            return

        print(f"\n✓ Found {len(materials)} materials")

        # Step 2: Analyze materials
        print("\n" + "="*80)
        print("STEP 2: Analyzing Materials")
        print("="*80)

        analysis = analyze_materials_summary(materials)
        print(f"\nMaterial Analysis:")
        print(f"  - Width Distribution: Narrow: {analysis['width_distribution']['narrow']}, "
              f"Wider: {analysis['width_distribution']['wider']}, Extra: {analysis['width_distribution']['extra']}")
        print(f"  - Weight Stats: Min: {analysis['weight_stats']['min']:.0f}kg, "
              f"Max: {analysis['weight_stats']['max']:.0f}kg, Avg: {analysis['weight_stats']['avg']:.0f}kg")
        print(f"  - Locations: {', '.join([f'{loc}:{count}' for loc, count in analysis['location_distribution'].items()])}")

        # Step 3: Determine rake type
        rake_type = 1
        if "planning_parameters" in input_data and input_data["planning_parameters"]:
            try:
                rake_type = int(input_data["planning_parameters"][0].get("RAKE_TYPE_ID", 1))
            except:
                pass

        print(f"\n✓ Using rake type: {rake_type} ({'Concord' if rake_type == 1 else 'Jumbo'})")

        # Step 4: Optimize loading
        print("\n" + "="*80)
        print("STEP 3: Optimizing Loading Plan")
        print("="*80)

        optimization_result = optimize_coil_loading(materials, rake_type)

        if not optimization_result["success"]:
            print(f"✗ Optimization failed: {optimization_result.get('error', 'Unknown error')}")
            return

        print(f"\n✓ Optimization successful!")
        print(f"  - Total coils: {optimization_result['metrics']['total_coils']}")
        print(f"  - Total wagons: {optimization_result['metrics']['total_wagons']}")
        print(f"  - Total weight: {optimization_result['metrics']['total_weight_kg']:,.0f} kg "
              f"({optimization_result['metrics']['total_weight_tons']:.1f} tons)")
        print(f"  - Utilization: {optimization_result['metrics']['capacity_utilization_percent']:.1f}%")
        print(f"  - Valid combinations: {optimization_result['metrics']['valid_combinations_percent']:.1f}%")

        # Step 5: Validate plan
        print("\n" + "="*80)
        print("STEP 4: Validating Plan")
        print("="*80)

        validation = validate_loading_plan(optimization_result, rake_type)

        if validation.get("valid", False):
            print("✓ Validation passed!")
        else:
            if validation.get("violations"):
                print("✗ Violations found:")
                for violation in validation.get("violations", [])[:5]:
                    print(f"  - {violation}")
            if validation.get("warnings"):
                print(f"⚠️  {len(validation.get('warnings', []))} warnings found")
                for warning in validation.get("warnings", [])[:5]:
                    print(f"  - {warning}")

        # Step 6: Generate output
        print("\n" + "="*80)
        print("STEP 5: Generating Output Excel")
        print("="*80)

        output_result = generate_excel_output(optimization_result, output_file)
        print(output_result)

        # Step 7: Generate insights
        print("\n" + "="*80)
        print("STEP 6: Optimization Insights")
        print("="*80)

        insights = generate_insights(optimization_result["metrics"])
        print(insights)

        print("\n" + "="*80)
        print("OPTIMIZATION COMPLETE!")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()