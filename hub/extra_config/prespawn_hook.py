def _define_resources(choices, node_info):
    """Compute resource allocation based on selected GPU type and number of GPUs."""

    num_gpus = int(choices.get("GPUNum", 0))
    if num_gpus == 0:
        return {}

    # get node info
    selected_node = choices.get("Node")
    node_data = next((n for n in node_info if str(n["node"]) == selected_node), None)

    # fraction of GPUs selected
    frac_gpus = num_gpus / node_data["num_gpus"]

    # compute resouces per gpu
    cpu = node_data["cpu_threads"] * frac_gpus
    mem = (
        node_data["gb_memory"] * 0.95 * frac_gpus
    )  # prevent max from being all of the memory

    return {
        "cpu_guarantee": 12,
        "cpu_limit": max(cpu, 12),
        "mem_guarantee": "12G",
        "mem_limit": f"{max(mem, 12)}G",
    }


def set_spawner_resources(spawner, CONFIG):
    """Pre-spawn hook to set resource limits based on profile selections."""
    profile_options = spawner.user_options

    # compute resource overrides
    resource_overrides = _define_resources(profile_options, CONFIG["node_info"])

    # apply changes to the spawner
    for key, value in resource_overrides.items():
        setattr(spawner, key, value)
