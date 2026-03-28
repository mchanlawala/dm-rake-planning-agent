# main.py
"""
Main entry point for Rake Planning Optimization System
"""

import os
import sys
import traceback
from typing import List, Tuple
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules
from config import ConfigManager
from utils import ExcelHandler, Validator
from optimizers import RakeOptimizer
from llm import InsightsGenerator

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

# Load environment variables
load_dotenv()


def initialize_llm(config):
    """Initialize LLM based on configuration"""
    llm_config = config.get_llm_config()
    preferred = llm_config.get('preferred_model', 'ollama')

    model = None
    llm_type = None

    # Try preferred model first
    if preferred == 'ollama' and OLLAMA_AVAILABLE:
        try:
            model = ChatOllama(
                model=llm_config.get('ollama_model', 'llama3.2'),
                temperature=llm_config.get('temperature', 0)
            )
            llm_type = "Ollama"
            print("✓ Ollama model loaded successfully")
        except Exception as e:
            print(f"⚠️  Ollama not available: {e}")

    if model is None and preferred == 'openai' and OPENAI_AVAILABLE:
        try:
            if os.getenv("OPENAI_API_KEY"):
                model = ChatOpenAI(
                    model=llm_config.get('openai_model', 'gpt-4o-mini'),
                    temperature=llm_config.get('temperature', 0)
                )
                llm_type = "OpenAI"
                print("✓ OpenAI model loaded successfully")
            else:
                print("⚠️  No OpenAI API key found")
        except Exception as e:
            print(f"⚠️  OpenAI not available: {e}")

    # Try fallback
    if model is None and OLLAMA_AVAILABLE:
        try:
            model = ChatOllama(model="llama3.2", temperature=0)
            llm_type = "Ollama"
            print("✓ Ollama model loaded as fallback")
        except:
            pass

    if model is None and OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        try:
            model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            llm_type = "OpenAI"
            print("✓ OpenAI model loaded as fallback")
        except:
            pass

    if model is None:
        print("⚠️  No LLM available. Optimization will continue without insights.")
        llm_type = "None"

    return model, llm_type


def get_valid_combinations_tuples(config) -> List[Tuple[int, int, int]]:
    """Get valid combinations as tuples for the optimizer"""
    combinations = config.get_valid_combinations()
    valid_combos = []
    for combo in combinations:
        valid_combos.append((combo['narrow'], combo['wider'], combo['extra']))
    return valid_combos


def main():
    """Main execution function"""
    print("=" * 80)
    print("RAKE PLANNING OPTIMIZATION SYSTEM")
    print("=" * 80)

    try:
        # Load configuration
        print("\nLoading configuration...")
        config = ConfigManager("config.yaml")

        # Initialize LLM
        model, llm_type = initialize_llm(config)
        print(f"LLM Status: {llm_type if llm_type else 'None'}")

        # Initialize components
        excel_handler = ExcelHandler(config)
        validator = Validator()
        insights_generator = InsightsGenerator(model, llm_type)

        # Read input file
        print("\n" + "="*80)
        print("STEP 1: Reading Input File")
        print("="*80)

        input_data = excel_handler.read_input()

        if "error" in input_data:
            print(f"✗ Error: {input_data['error']}")
            return

        materials = input_data.get("materials", [])

        if not materials:
            print("✗ No materials found in the input file!")
            return

        print(f"\n✓ Found {len(materials)} materials")

        # Load Excel configuration to override YAML
        excel_config = config.load_excel_config(config.get_input_path())

        # Get valid combinations as tuples
        valid_combinations = get_valid_combinations_tuples(config)

        # Determine rake type
        rake_type = 1
        if input_data.get("planning_parameters"):
            try:
                rake_type = int(input_data["planning_parameters"][0].get("RAKE_TYPE_ID", 1))
            except:
                pass

        print(f"✓ Using rake type: {rake_type} ({'Concord' if rake_type == 1 else 'Jumbo'})")

        # Create optimizer
        optimizer = RakeOptimizer(config, valid_combinations)

        # Optimize loading
        print("\n" + "="*80)
        print("STEP 2: Optimizing Loading Plan")
        print("="*80)

        optimization_result = optimizer.optimize(materials, rake_type)

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

        # Validate plan
        print("\n" + "="*80)
        print("STEP 3: Validating Plan")
        print("="*80)

        rake_config = {
            1: config.get_rake_type(1),
            2: config.get_rake_type(2)
        }

        validation = validator.validate_plan(optimization_result, rake_type, rake_config)

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

        # Generate output
        print("\n" + "="*80)
        print("STEP 4: Generating Output Excel")
        print("="*80)

        output_result = excel_handler.write_output(optimization_result)
        print(output_result)

        # Generate insights
        print("\n" + "="*80)
        print("STEP 5: Optimization Insights")
        print("="*80)

        insights = insights_generator.generate(optimization_result["metrics"])
        print(insights)

        print("\n" + "="*80)
        print("OPTIMIZATION COMPLETE!")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()