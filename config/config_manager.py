# config/config_manager.py
"""
Configuration Manager for Rake Planning System
Handles loading and accessing configuration from YAML file and Excel inputs
"""

import os
import yaml
from typing import Dict, Any, Optional, List
import pandas as pd


class ConfigManager:
    """Manages configuration for the rake planning system"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration manager

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path
        self.config = self._load_yaml_config()
        self.excel_config = None

    def _load_yaml_config(self) -> Dict:
        """Load YAML configuration file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_excel_config(self, excel_path: str) -> Dict:
        """
        Load configuration from Excel file (overrides YAML settings)

        Args:
            excel_path: Path to Excel input file

        Returns:
            Dictionary with Excel-based configuration
        """
        if not os.path.exists(excel_path):
            return {}

        excel_config = {}

        # Load rake constraints from Excel
        try:
            rake_df = pd.read_excel(
                excel_path,
                sheet_name=self.config['input']['rake_constraint_sheet'],
                header=1
            )
            rake_df.columns = [str(col).strip() for col in rake_df.columns]

            rake_types = {}
            for _, row in rake_df.iterrows():
                rake_id = int(row.get('RAKE_TYPE_ID', 0))
                if rake_id > 0:
                    rake_types[rake_id] = {
                        'name': row.get('RAKE_TYPE_NAME', ''),
                        'min_weight': float(row.get('RAKE_MIN_WEIGHT', 0)),
                        'max_weight': float(row.get('RAKE_MAX_WEIGHT', 0)),
                        'total_capacity': float(row.get('TOTAL_CAPACITY', 0)),
                        'no_wagons': int(row.get('NO_WAGONS', 0))
                    }
            excel_config['rake_types'] = rake_types
        except Exception as e:
            print(f"Warning: Could not load rake constraints from Excel: {e}")

        # Load wagon constraints from Excel
        try:
            wagon_df = pd.read_excel(
                excel_path,
                sheet_name=self.config['input']['wagon_constraint_sheet'],
                header=1
            )
            wagon_df.columns = [str(col).strip() for col in wagon_df.columns]

            wagon_constraints = {}
            for _, row in wagon_df.iterrows():
                width_range = row.get('WIDTH_RANGE_NAME', '').upper()
                wagon_constraints[width_range] = {
                    'id': int(row.get('ID', 0)),
                    'name': width_range,
                    'min_width': float(row.get('WIDTH_MIN_RANGE', 0)),
                    'max_width': float(row.get('WIDTH_MAX_RANGE', 0)),
                    'max_coils': int(row.get('NUMBER_OF_COIL', 0))
                }
            excel_config['wagon_constraints'] = wagon_constraints
        except Exception as e:
            print(f"Warning: Could not load wagon constraints from Excel: {e}")

        # Load width combinations from Excel
        try:
            combo_df = pd.read_excel(
                excel_path,
                sheet_name=self.config['input']['width_combinations_sheet'],
                header=1
            )
            combo_df.columns = [str(col).strip() for col in combo_df.columns]

            combinations = []
            for _, row in combo_df.iterrows():
                combinations.append({
                    'id': int(row.get('ID', 0)),
                    'narrow': int(row.get('NARROW', 0)),
                    'wider': int(row.get('WIDER', 0)),
                    'extra': int(row.get('EXTRA', 0)),
                    'remark': row.get('REMARK', '')
                })
            excel_config['valid_combinations'] = combinations
        except Exception as e:
            print(f"Warning: Could not load width combinations from Excel: {e}")

        self.excel_config = excel_config
        return excel_config

    def get_rake_type(self, rake_id: int) -> Optional[Dict]:
        """Get rake type configuration"""
        if self.excel_config and 'rake_types' in self.excel_config:
            return self.excel_config['rake_types'].get(rake_id)
        return self.config['rake_types'].get(rake_id)

    def get_wagon_constraint(self, width_range: str) -> Optional[Dict]:
        """Get wagon constraint for width range"""
        width_range = width_range.upper()
        if self.excel_config and 'wagon_constraints' in self.excel_config:
            return self.excel_config['wagon_constraints'].get(width_range)

        # Map from YAML config
        for key, value in self.config['wagon_constraints'].items():
            if key.upper() == width_range:
                return value
        return None

    def get_valid_combinations(self) -> List[Dict]:
        """Get valid width combinations"""
        if self.excel_config and 'valid_combinations' in self.excel_config:
            return self.excel_config['valid_combinations']
        return self.config['valid_combinations']

    def get_max_coils_per_wagon(self) -> int:
        """Get maximum coils per wagon"""
        return self.config['optimization']['max_coils_per_wagon']

    def get_input_path(self) -> str:
        """Get input Excel file path"""
        return self.config['input']['excel_path']

    def get_output_path(self) -> str:
        """Get output Excel file path"""
        return self.config['output']['excel_path']

    def get_llm_config(self) -> Dict:
        """Get LLM configuration"""
        return self.config['llm']