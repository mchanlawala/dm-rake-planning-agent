# utils/excel_handler.py
"""
Excel File Handler for Rake Planning System
"""

import pandas as pd
import os
from typing import Dict, List, Any


class ExcelHandler:
    """Handles reading and writing Excel files"""

    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config

    def read_input(self, file_path: str = None) -> Dict[str, Any]:
        """
        Read input Excel file

        Args:
            file_path: Path to input Excel file

        Returns:
            Dictionary with all data
        """
        if file_path is None:
            file_path = self.config.get_input_path()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")

        result = {}

        # Read Material sheet
        try:
            materials = self._read_material_sheet(file_path)
            result["materials"] = materials
        except Exception as e:
            print(f"Error reading Material sheet: {e}")
            result["materials"] = []

        # Read Rake Constraint sheet
        try:
            rake_constraints = self._read_rake_constraint_sheet(file_path)
            result["rake_constraints"] = rake_constraints
        except Exception as e:
            print(f"Error reading Rake Constraint sheet: {e}")
            result["rake_constraints"] = []

        # Read Planning Parameter sheet
        try:
            planning_parameters = self._read_planning_parameter_sheet(file_path)
            result["planning_parameters"] = planning_parameters
        except Exception as e:
            print(f"Error reading Planning Parameter sheet: {e}")
            result["planning_parameters"] = []

        # Read Wagon Constraint sheet
        try:
            wagon_constraints = self._read_wagon_constraint_sheet(file_path)
            result["wagon_constraints"] = wagon_constraints
        except Exception as e:
            print(f"Error reading Wagon Constraint sheet: {e}")
            result["wagon_constraints"] = []

        # Read Width Range Combinations sheet
        try:
            width_combinations = self._read_width_combinations_sheet(file_path)
            result["width_combinations"] = width_combinations
        except Exception as e:
            print(f"Error reading Width Range Combinations sheet: {e}")
            result["width_combinations"] = []

        return result

    def _read_material_sheet(self, file_path: str) -> List[Dict]:
        """Read Material sheet"""
        # Try different header rows
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

        # Filter out rows with empty batch numbers
        materials = [m for m in materials if m.get('BATCH_NUMBER') and not pd.isna(m.get('BATCH_NUMBER'))]

        return materials

    def _read_rake_constraint_sheet(self, file_path: str) -> List[Dict]:
        """Read Rake Constraint sheet"""
        rake_df = pd.read_excel(file_path, sheet_name='Rake Constraint', header=1)
        rake_df.columns = [str(col).strip() for col in rake_df.columns]
        rake_df = rake_df.dropna(how='all')
        return rake_df.to_dict('records')

    def _read_planning_parameter_sheet(self, file_path: str) -> List[Dict]:
        """Read Planning Parameter sheet"""
        planning_df = pd.read_excel(file_path, sheet_name='Planning Parameter', header=1)
        planning_df.columns = [str(col).strip() for col in planning_df.columns]
        planning_df = planning_df.dropna(how='all')
        return planning_df.to_dict('records')

    def _read_wagon_constraint_sheet(self, file_path: str) -> List[Dict]:
        """Read Wagon Constraint sheet"""
        wagon_df = pd.read_excel(file_path, sheet_name='Wagon Constraint', header=1)
        wagon_df.columns = [str(col).strip() for col in wagon_df.columns]
        wagon_df = wagon_df.dropna(how='all')
        return wagon_df.to_dict('records')

    def _read_width_combinations_sheet(self, file_path: str) -> List[Dict]:
        """Read Width Range Combinations sheet"""
        combo_df = pd.read_excel(file_path, sheet_name='Width Range Combinations', header=1)
        combo_df.columns = [str(col).strip() for col in combo_df.columns]
        combo_df = combo_df.dropna(how='all')
        return combo_df.to_dict('records')

    def write_output(self, plan: Dict, output_path: str = None) -> str:
        """
        Write optimized plan to Excel

        Args:
            plan: Optimization result dictionary
            output_path: Output file path

        Returns:
            Status message
        """
        if output_path is None:
            output_path = self.config.get_output_path()

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
            # Main mapping sheet
            df.to_excel(writer, sheet_name=self.config.config['output']['mapping_sheet'], index=False)

            # Metrics sheet
            metrics = plan.get("metrics", {})
            metrics_df = pd.DataFrame([metrics])
            metrics_df.to_excel(writer, sheet_name=self.config.config['output']['metrics_sheet'], index=False)

            # Wagon summary sheet
            summary = df.groupby('WAGON_ID').agg({
                'STOCK_WEIGHT': 'sum',
                'STOCK_WIDTH': 'count',
                'LOCATION': 'first'
            }).reset_index()
            summary.columns = ['WAGON_ID', 'TOTAL_WEIGHT', 'COILS_COUNT', 'LOCATION']

            # Get rake max weight from config
            rake_id = int(plan.get('wagons', [{}])[0].get('RAKE_TYPE_ID', 1)) if plan.get('wagons') else 1
            rake = self.config.get_rake_type(rake_id)
            max_wagon_weight = rake['max_weight'] if rake else 63000

            summary['UTILIZATION_PERCENT'] = (summary['TOTAL_WEIGHT'] / max_wagon_weight) * 100
            summary.to_excel(writer, sheet_name=self.config.config['output']['summary_sheet'], index=False)

        return f"SUCCESS: Generated output file\nPath: {output_path}\nWagons: {len(df['WAGON_ID'].unique())}\nCoils: {len(df)}"