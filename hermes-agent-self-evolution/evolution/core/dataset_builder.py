"""Evaluation dataset generation for hermes-agent-self-evolution.

Sources:
A) Synthetic generation — LLM reads a skill/tool/prompt and generates test cases
B) SessionDB mining — extract real usage patterns and score with LLM-as-judge
C) Golden sets — hand-curated JSONL files
"""

import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import dspy

from evolution.core.config import EvolutionConfig


@dataclass
class EvalExample:
    """A single evaluation example."""
    task_input: str  # What the user asks
    expected_behavior: str  # Rubric — what a good response looks like
    difficulty: str = "medium"  # easy, medium, hard
    category: str = "general"  # Category for stratified eval
    source: str = "synthetic"  # synthetic, sessiondb, golden

    def to_dict(self) -> dict:
        return {
            "task_input": self.task_input,
            "expected_behavior": self.expected_behavior,
            "difficulty": self.difficulty,
            "category": self.category,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvalExample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EvalDataset:
    """Train/val/holdout split of evaluation examples."""
    train: list[EvalExample] = field(default_factory=list)
    val: list[EvalExample] = field(default_factory=list)
    holdout: list[EvalExample] = field(default_factory=list)

    @property
    def all_examples(self) -> list[EvalExample]:
        return self.train + self.val + self.holdout

    def save(self, path: Path):
        """Save dataset splits to JSONL files."""
        path.mkdir(parents=True, exist_ok=True)
        for split_name, split_data in [("train", self.train), ("val", self.val), ("holdout", self.holdout)]:
            with open(path / f"{split_name}.jsonl", "w") as f:
                for ex in split_data:
                    f.write(json.dumps(ex.to_dict()) + "\n")

    @classmethod
    def load(cls, path: Path) -> "EvalDataset":
        """Load dataset splits from JSONL files."""
        dataset = cls()
        for split_name in ["train", "val", "holdout"]:
            split_file = path / f"{split_name}.jsonl"
            if split_file.exists():
                examples = []
                with open(split_file) as f:
                    for line in f:
                        if line.strip():
                            examples.append(EvalExample.from_dict(json.loads(line)))
                setattr(dataset, split_name, examples)
        return dataset

    def to_dspy_examples(self, split: str = "train") -> list[dspy.Example]:
        """Convert a split to DSPy Example objects."""
        data = getattr(self, split)
        return [
            dspy.Example(
                task_input=ex.task_input,
                expected_behavior=ex.expected_behavior,
            ).with_inputs("task_input")
            for ex in data
        ]


class SyntheticDatasetBuilder:
    """Generate evaluation datasets using a strong LLM.

    Reads the target artifact (skill file, tool description, etc.)
    and generates realistic (task_input, expected_behavior) pairs.
    """

    class GenerateTestCases(dspy.Signature):
        """Generate realistic evaluation test cases for an agent skill or tool.

        Given the full text of a skill/tool description, generate diverse test cases
        that would exercise different aspects of the skill. Each test case should include:
        - A realistic task_input (what a user would actually ask)
        - An expected_behavior rubric (what a good response should contain/do, NOT exact text)
        - A difficulty level (easy, medium, hard)
        - A category (what aspect of the skill this tests)
        """
        artifact_text: str = dspy.InputField(desc="The full text of the skill/tool/prompt being tested")
        artifact_type: str = dspy.InputField(desc="Type: 'skill', 'tool_description', or 'prompt_section'")
        num_cases: int = dspy.InputField(desc="Number of test cases to generate")
        test_cases: str = dspy.OutputField(desc="JSON array of test cases, each with: task_input, expected_behavior, difficulty, category")

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.generator = dspy.Predict(
            self.GenerateTestCases,
        )

    @staticmethod
    def _parse_markdown_list(text: str) -> list | None:
        """Parse markdown numbered list format (fallback when LLM doesn't output JSON).

        Handles format like:
        1. **Title**
           Input: `"query"`
           Expected: description

        Or Chinese/ alternative formats:
        1. **Title**
           - 输入：用户消息"query"
           - 预期行为：description

        Or any variation with numbered items and input/expected-like patterns.
        """
        import re
        lines = text.strip().split('\n')
        cases = []
        current = {}

        for line in lines:
            # Match numbered items: "1. **Title**" or "1. Title"
            m = re.match(r'^\d+\.\s+\*{0,2}(.+?)\*{0,2}\s*$', line)
            if m and current:
                if current.get('task_input') and current.get('expected_behavior'):
                    cases.append(current)
                    current = {}
                continue

            # Match various input formats:
            # Input: `"... "`
            # 输入：用户消息"..."
            # 输入："..."
            m = re.match(r'\s*(?:Input|输入)(?::|：)\s*(?:用户消息)?[`"“‘]*(.+?)[`"”’]', line)
            if m:
                val = m.group(1).strip()
                if val:
                    current['task_input'] = val
                continue

            # Match various expected behavior formats:
            # Expected: description
            # 预期行为：description
            m = re.match(r'\s*(?:Expected|预期行为)(?::|：)\s*(.+)', line)
            if m:
                val = m.group(1).strip()
                if val:
                    current['expected_behavior'] = val
                continue

            # Fallback for "- input/expected" pattern where both are inline
            m = re.match(r'\s*[-*]\s+(?:Input|输入)(?::|：)\s*(?:用户消息)?[`"“‘]*(.+?)[`"”’]', line)
            if m:
                val = m.group(1).strip()
                if val:
                    current['task_input'] = val
                continue

            m = re.match(r'\s*[-*]\s+(?:Expected|预期行为)(?::|：)\s*(.+)', line)
            if m:
                val = m.group(1).strip()
                if val:
                    current['expected_behavior'] = val
                continue

        # Don't forget the last one
        if current and current.get('task_input') and current.get('expected_behavior'):
            cases.append(current)

        # Fill in defaults
        if not cases:
            return None

        result = []
        for c in cases:
            result.append({
                'task_input': c['task_input'],
                'expected_behavior': c['expected_behavior'],
                'difficulty': 'medium',
                'category': 'general',
            })

        return result

    def generate(
        self,
        artifact_text: str,
        artifact_type: str = "skill",
        num_cases: Optional[int] = None,
    ) -> EvalDataset:
        """Generate a full eval dataset with train/val/holdout splits."""

        n = num_cases or self.config.eval_dataset_size

        # Use the already-configured global DSPy LM (which has api_base set)
        # rather than creating a new one without api_base
        with dspy.context():
            result = self.generator(
                artifact_text=artifact_text,
                artifact_type=artifact_type,
                num_cases=n,
            )

        # Parse the generated test cases
        cases_raw = None
        raw = result.test_cases

        import re

        # Strategy 0: strip markdown code fences first
        text = raw.strip()
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```$', '', text)
        text = text.strip()

        # Try direct parse first
        try:
            cases_raw = json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 1: find the outermost brackets
        if cases_raw is None:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                try:
                    cases_raw = json.loads(match.group())
                except json.JSONDecodeError:
                    cases_raw = None

        # Strategy 2: fix common LLM JSON quirks (single-quoted keys, trailing commas)
        if cases_raw is None:
            fixed = text
            # Fix Python-style single quotes → JSON double quotes
            # 1. Fix keys: 'key': -> "key":
            fixed = re.sub(r"'([a-zA-Z_][a-zA-Z0-9_]*)'\s*:", lambda m: '"' + m.group(1) + '":', fixed)
            # 2. Fix values: : 'value' -> : "value" (with internal quote escaping)
            def _fix_value(m):
                val = m.group(1)
                val = val.replace('\\', '\\\\')
                val = val.replace('"', '\\"')
                return ': "' + val + '"'
            fixed = re.sub(r":\s*'([^']*)'", _fix_value, fixed)
            # 3. Remove trailing commas before ] or }
            fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
            try:
                cases_raw = json.loads(fixed)
            except json.JSONDecodeError:
                cases_raw = None

        # Strategy 3: parse markdown numbered list format
        if cases_raw is None:
            cases_raw = self._parse_markdown_list(text)

        if cases_raw is None:
            raise ValueError(
                f"Could not parse test cases from LLM output.\n"
                f"Raw[:200]: {raw[:200]}\n"
                f"After strip+code-fence-removal[:200]: {text[:200]}"
            )

        examples = [
            EvalExample(
                task_input=c.get("task_input", ""),
                expected_behavior=c.get("expected_behavior", ""),
                difficulty=c.get("difficulty", "medium"),
                category=c.get("category", "general"),
                source="synthetic",
            )
            for c in cases_raw
            if c.get("task_input") and c.get("expected_behavior")
        ]

        # Shuffle and split
        random.shuffle(examples)
        n_total = len(examples)
        n_train = max(1, int(n_total * self.config.train_ratio))
        n_val = max(1, int(n_total * self.config.val_ratio))

        return EvalDataset(
            train=examples[:n_train],
            val=examples[n_train:n_train + n_val],
            holdout=examples[n_train + n_val:],
        )


class GoldenDatasetLoader:
    """Load hand-curated evaluation datasets from JSONL files."""

    @staticmethod
    def load(path: Path) -> EvalDataset:
        """Load a golden dataset. If no splits exist, auto-split the single file."""
        if (path / "train.jsonl").exists():
            return EvalDataset.load(path)

        # Single file — auto-split
        golden_file = path if path.suffix == ".jsonl" else path / "golden.jsonl"
        if not golden_file.exists():
            raise FileNotFoundError(f"No golden dataset found at {golden_file}")

        examples = []
        with open(golden_file) as f:
            for line in f:
                if line.strip():
                    examples.append(EvalExample.from_dict(json.loads(line)))

        random.shuffle(examples)
        n = len(examples)
        n_train = max(1, int(n * 0.5))
        n_val = max(1, int(n * 0.25))

        return EvalDataset(
            train=examples[:n_train],
            val=examples[n_train:n_train + n_val],
            holdout=examples[n_train + n_val:],
        )
