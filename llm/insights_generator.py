# llm/insights_generator.py
"""
LLM-based insights generator for optimization results
"""

from typing import Dict


class InsightsGenerator:
    """Generates AI-powered insights about optimization results"""

    def __init__(self, model, llm_type: str):
        """
        Initialize insights generator

        Args:
            model: LLM model instance
            llm_type: Type of LLM (Ollama, OpenAI, None)
        """
        self.model = model
        self.llm_type = llm_type

    def generate(self, metrics: Dict) -> str:
        """
        Generate insights using LLM

        Args:
            metrics: Optimization metrics dictionary

        Returns:
            Insights text
        """
        if not self.model or self.llm_type == "None":
            return self._get_fallback_insights(metrics)

        try:
            prompt = f"""
            As a steel plant logistics expert, analyze these optimization results:
            
            - Total coils: {metrics.get('total_coils', 0)}
            - Total wagons: {metrics.get('total_wagons', 0)}
            - Total weight: {metrics.get('total_weight_kg', 0):,.0f} kg
            - Utilization: {metrics.get('capacity_utilization_percent', 0):.1f}%
            - Valid combinations: {metrics.get('valid_combinations_percent', 0):.1f}%
            - Rake type: {metrics.get('rake_type', 'Unknown')}
            - Average wagon weight: {metrics.get('average_wagon_weight', 0):,.0f} kg
            - Target wagon weight: {metrics.get('target_wagon_weight', 0):,.0f} kg
            
            Provide 3-4 bullet points with insights and recommendations for improvement.
            """

            response = self.model.invoke(prompt)
            return response.content

        except Exception as e:
            return f"Unable to generate insights: {str(e)}\n\n{self._get_fallback_insights(metrics)}"

    def _get_fallback_insights(self, metrics: Dict) -> str:
        """Get fallback insights when LLM is not available"""
        utilization = metrics.get('capacity_utilization_percent', 0)
        valid_combos = metrics.get('valid_combinations_percent', 0)
        avg_weight = metrics.get('average_wagon_weight', 0)
        target_weight = metrics.get('target_wagon_weight', 0)

        insights = f"""
Optimization Insights:
• Successfully loaded {metrics.get('total_coils', 0)} coils into {metrics.get('total_wagons', 0)} wagons
• Weight utilization: {utilization:.1f}% {'(Good)' if utilization > 85 else '(Needs improvement)'}
• Valid combinations: {valid_combos:.1f}% {'(Excellent)' if valid_combos > 80 else '(Consider optimizing width grouping)'}
• Average wagon weight: {avg_weight:,.0f} kg (Target: {target_weight:,.0f} kg)
• Efficiency score: {'High' if utilization > 85 and valid_combos > 80 else 'Medium' if utilization > 70 else 'Low'}

Recommendations:
"""

        if utilization < 85:
            insights += "• Consider heavier coils to improve weight utilization\n"
        if valid_combos < 80:
            insights += "• Group similar width coils together for better combination validity\n"
        if avg_weight < target_weight * 0.9:
            insights += "• Optimize wagon loading to reach target weight\n"

        return insights