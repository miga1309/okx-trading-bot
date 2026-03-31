from dataclasses import dataclass


@dataclass
class RuntimeFlags:
    demo_mode: bool = True
    dry_bootstrap: bool = False
