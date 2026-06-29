"""
Mock Sandbox Simulator for generating ABC execution traces.
"""
import json
from pathlib import Path


class SandboxSimulator:
    def __init__(self, dataset_path: str | Path = "docs/abc_canonical_prompts_dataset.json"):
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Canonical dataset not found at {self.dataset_path}")
            
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            self.prompts = json.load(f)

    def execute_skill(self, skill_name: str) -> list[str]:
        """
        Simulate the execution of a skill against all canonical prompts.
        Returns a list of trace strings.
        """
        traces = []
        for p in self.prompts:
            trace = (
                f"Skill: {skill_name}\n"
                f"Prompt ID: {p.get('prompt_id')}\n"
                f"Category: {p.get('category')}\n"
                f"User Instruction: {p.get('prompt')}\n"
                f"Agent Tool Calls: {', '.join(p.get('expected_tool_calls', []))}\n"
                f"Agent Output: {p.get('expected_output_pattern')}\n"
            )
            traces.append(trace)
        return traces
