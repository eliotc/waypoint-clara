"""First adapter: replay explicit synthetic traces, with no model or DB calls.

A future live adapter must return this same validated trace contract while
preserving model output, tool arguments/results, cards and observed side effects.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Protocol


class Adapter(Protocol):
    def run(self, scenario: dict, persona: dict) -> dict: ...


class FixtureAdapter:
    def __init__(self, fixture: dict):
        self.traces = {trace["scenario_id"]: trace for trace in fixture["traces"]}
        if len(self.traces) != len(fixture["traces"]):
            raise ValueError("Duplicate scenario IDs in fixture")

    def run(self, scenario: dict, persona: dict) -> dict:
        if scenario["scenario_id"] not in self.traces:
            raise ValueError("Missing fixture trace for scenario")
        trace = deepcopy(self.traces[scenario["scenario_id"]])
        if [turn["user"] for turn in trace["turns"]] != scenario["user_turns"]:
            raise ValueError("Fixture user turns differ from the scenario")
        return trace
