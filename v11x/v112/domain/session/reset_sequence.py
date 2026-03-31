def build_reset_sequence() -> list[str]:
    return ["pause_runtime", "flush_state", "reset_ui_state"]
