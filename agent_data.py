"""Load the clean carts and apply the simulation setting. Shared by the agent, rules and dashboard."""
import os
import re

from prepare_data import BASE, load_carts

POLICY_PATH = os.path.join(BASE, "prompts", "policies.md")


def assume_subscribed():
    """Read 'Assume carts are subscribed to email: yes/no' from policies.md. Missing means no."""
    if not os.path.exists(POLICY_PATH):
        return False
    with open(POLICY_PATH, encoding="utf-8") as f:
        m = re.search(r"Assume carts are subscribed to email:\s*(yes|no)", f.read(), re.I)
    return bool(m) and m.group(1).lower() == "yes"


def load_for_app():
    """Carts with marketing_state filled in from the simulation setting, plus dataset stats."""
    carts, stats = load_carts()
    state = "SUBSCRIBED" if assume_subscribed() else "UNKNOWN"
    for c in carts:
        c["marketing_state"] = state
    return carts, stats
