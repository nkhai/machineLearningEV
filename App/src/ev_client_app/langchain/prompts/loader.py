"""
Prompt management for EV battery simulation.

Loads prompt templates from YAML files, handles LangChain variable escaping,
and provides a factory for ChatPromptTemplate objects.

Usage:
    from prompts.loader import get_langchain_prompt
    prompt = get_langchain_prompt("AC_CHARGING")
"""

import os
from pathlib import Path

import yaml
from langchain_core.prompts import ChatPromptTemplate

# ================================================================
# YAML FILE LOADING
# ================================================================

current_dir = Path(__file__).resolve().parent

# Load prompt YAMLs
charging_yaml_path = current_dir / "fast_charging.yaml"
with open(charging_yaml_path, "r", encoding="utf-8") as f:
    CHARGING_PROMPT_TEXT = f.read()

driving_yaml_path = current_dir / "urban_driving.yaml"
with open(driving_yaml_path, "r", encoding="utf-8") as f:
    DRIVING_PROMPT_TEXT = f.read()

highway_yaml_path = current_dir / "highway_driving.yaml"
with open(highway_yaml_path, "r", encoding="utf-8") as f:
    HIGHWAY_PROMPT_TEXT = f.read()

home_charging_yaml_path = current_dir / "home_charging.yaml"
with open(home_charging_yaml_path, "r", encoding="utf-8") as f:
    HOME_CHARGING_PROMPT_TEXT = f.read()


# ================================================================
# PROMPT REGISTRY
# ================================================================

PROMPT_REGISTRY = {
    "FAST_CHARGING": CHARGING_PROMPT_TEXT,
    "URBAN_CRUISE": DRIVING_PROMPT_TEXT,
    "HIGHWAY_CRUISE": HIGHWAY_PROMPT_TEXT,
    "HOME_CHARGING": HOME_CHARGING_PROMPT_TEXT,
}

# ================================================================
# UTILITY FORMATTER
# ================================================================

def make_langchain_safe(raw_prompt: str) -> str:
    """
    Handles LangChain double-brace conflicts.

    The prompt contains {context_records} for LangChain variable substitution,
    and {{/}} for JSON examples in the prompt text.

    Steps:
    1. Temporarily replace valid LangChain variables
    2. Normalize all {{ and }} back to { and }
    3. Escape ALL remaining { and } (JSON examples, etc.)
    4. Restore LangChain variables
    """
    allowed_vars = [
        "context_records",
        "car_id",
        "car_model",
        "label",
        "mileage",
        "capacity",
        "last_soc"
    ]

    safe_text = raw_prompt

    # 1. Protect LangChain variables
    for var in allowed_vars:
        safe_text = safe_text.replace(f"{{{var}}}", f"@@@LANGCHAIN_VAR_{var}@@@")

    # 2. Normalize escaped braces
    safe_text = safe_text.replace("{{", "{").replace("}}", "}")

    # 3. Escape ALL remaining braces
    safe_text = safe_text.replace("{", "{{").replace("}", "}}")

    # 4. Restore LangChain variables
    for var in allowed_vars:
        safe_text = safe_text.replace(f"@@@LANGCHAIN_VAR_{var}@@@", f"{{{var}}}")

    return safe_text


# ================================================================
# TEMPLATE FACTORY
# ================================================================

def get_langchain_prompt(scenario: str) -> ChatPromptTemplate:
    """
    Build the ChatPromptTemplate for a specific EV battery simulation scenario.

    Args:
        scenario: Must be in PROMPT_REGISTRY (e.g. "AC_CHARGING", "URBAN_CRUISE",
                  "HIGHWAY_CRUISE", "HOME_CHARGING").

    Returns:
        ChatPromptTemplate: A ready-to-use LangChain template.
    """
    if scenario not in PROMPT_REGISTRY:
        valid_keys = ", ".join(PROMPT_REGISTRY.keys())
        raise ValueError(f"Unknown scenario: '{scenario}'. Valid scenarios are: {valid_keys}")

    raw_prompt = PROMPT_REGISTRY[scenario]
    safe_langchain_prompt = make_langchain_safe(raw_prompt)

    return ChatPromptTemplate.from_template(safe_langchain_prompt)
