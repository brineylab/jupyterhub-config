# modified from https://github.com/neurohackademy/nh2020-jupyterhub/blob/8bc0d8304d5090d3a1e21a038a68f0a940e31809/deployments/hub-neurohackademy-org/config/prod.yaml
# ref for profile_options: https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html


def _define_images(images, default):
    """Define the image choices"""
    return {
        "Image": {
            "display_name": "Image",
            "choices": {
                name: {
                    "display_name": name,
                    "default": (name == default),
                    "kubespawner_override": {"image": url},
                }
                for name, url in images.items()
            },
            "unlisted_choice": {
                "enabled": True,
                "display_name": "Enter custom image",
                "display_name_in_choices": "other - select to provide a custom image",
                "kubespawner_override": {
                    "image": "{value}",
                    "start_timeout": 600,  # increase timeout to allow new images to be pulled
                },
            },
        }
    }


def _define_num_gpus(gpu_counts):
    """Define choices for number of gpus"""
    return {
        "GPUNum": {
            "display_name": "Number of GPUs",
            "choices": {
                str(i): {
                    "display_name": str(i),
                    # config required to enable gpu: https://discourse.jupyter.org/t/set-runtimeclassname-for-gpu-enabled-images/21617/5
                    "kubespawner_override": (
                        {
                            "extra_resource_limits": {"nvidia.com/gpu": i},
                            "extra_pod_config": {"runtimeClassName": "nvidia"},
                        }
                        if i > 0
                        else {}
                    ),
                }
                for i in gpu_counts
            },
        }
    }


def _define_gpu_nodes(node_info):
    """Define node choices. Allows kubespawner override for dev profile."""
    return {
        "Node": {
            "display_name": "Node",
            "choices": {
                str(node["node"]): {
                    "display_name": str(node["node"]),
                    "kubespawner_override": node.get(
                        "kubespawner_override",
                        {
                            "node_selector": {
                                "kubernetes.io/hostname": str(node["node"])
                            }
                        },
                    ),
                }
                for node in node_info
            },
        }
    }


# image descriptions
image_des = """Choose your image.
                <ul>
                <li><b>datascience</b>: base data analysis environment (including interpreters for Python and R)</li>
                <li><b>deeplearning</b>: extends datascience environment to include ML libraries (including torch, deepspeed, and 🤗)</li>
                </ul>
            """


# define low resource CPU profile
def low_cpu_profile(CONFIG):
    return [
        {
            "display_name": "Low-Resource CPU Server",
            "description": "Use this profile to for smaller jobs and day-to-day use."
            + image_des,
            "profile_options": {
                **_define_images(CONFIG["images"], "datascience"),
            },
            "kubespawner_override": {
                "node_selector": {"node_profile": "low-cpu"},
                "cpu_guarantee": 16,
                "cpu_limit": 32,
                "mem_guarantee": "32G",
                "mem_limit": "64G",
            },
        }
    ]


# define high resource CPU profile
def high_cpu_profile(CONFIG):
    return [
        {
            "display_name": "High-Resource CPU Server",
            "description": "Use this profile to for larger jobs requiring more resources."
            + "Please remember to shut down your server after your job completes."
            + image_des,
            "profile_options": {
                **_define_images(CONFIG["images"], "datascience"),
            },
            "kubespawner_override": {
                "node_selector": {"node_profile": "cpu"},
                "cpu_guarantee": 16,
                "cpu_limit": 128,
                "mem_guarantee": "64G",
                "mem_limit": "512G",
            },
        }
    ]


# define GPU profile
def gpu_profile(CONFIG):
    # filter out admin only nodes
    node_info = CONFIG["node_info"].copy()
    filtered_nodes = [n for n in node_info if not n.get("admin_only", False)]

    return [
        {
            "display_name": "GPU Server",
            "description": image_des
            + "Reference the GPU availability below to select your node and number of GPUs.",
            "profile_options": {
                **_define_images(CONFIG["images"], "deeplearning"),
                **_define_gpu_nodes(filtered_nodes),
                **_define_num_gpus(CONFIG["gpu_counts"]),
            },
        }
    ]


# define volume access profile - for accessing workspace volume
# has low resources and no gpus
def volume_profile(CONFIG):
    return [
        {
            "display_name": "Volume Access",
            "description": (
                "Use this profile to access the workspace volume only. "
                "Resources are limited, so please don't try to run large jobs."
            ),
            "kubespawner_override": {
                "image": CONFIG["images"]["datascience"],
                "cpu_guarantee": 1,
                "cpu_limit": 12,
                "mem_guarantee": "1G",
                "mem_limit": "12G",
            },
        }
    ]


# dev profile (admin only)
# mostly useful for servers with gpus, to allow any number of gpus
def dev_profile(CONFIG, server_type):
    nodes = CONFIG["node_info"].copy()

    # add CPU node with kubespawner_override
    if server_type == "cpu-gpu":
        nodes.append(
            {
                "node": "CPU node",
                "kubespawner_override": {"node_selector": {"node_profile": "cpu"}},
            }
        )

    return [
        {
            "display_name": "Dev Profile (admin only)",
            "description": (
                "Set custom images, resources, etc for testing. "
                "Timeout is extended to 10mins if you provide a custom image."
            ),
            "profile_options": {
                **_define_images(CONFIG["images"], "datascience"),
                **_define_gpu_nodes(nodes),
                **_define_num_gpus(range(9)),
            },
        }
    ]


# return profile options based on the server type and config provided
def dynamic_options_form_withconfig(CONFIG):
    def dynamic_options_form(self):

        # generate profile list based on server type
        server_type = CONFIG["server_type"]
        if (
            server_type == "cpu-gpu"
        ):  # For default server -> CPU profiles, for named servers -> GPU profiles
            if self.name:
                self.profile_list = gpu_profile(CONFIG)
            else:
                self.profile_list = low_cpu_profile(CONFIG) + high_cpu_profile(CONFIG)
        elif server_type == "cpu-only":
            self.profile_list = low_cpu_profile(CONFIG) + high_cpu_profile(CONFIG)
        elif server_type == "gpu-only":
            self.profile_list = gpu_profile(CONFIG) + volume_profile(CONFIG)
        else:
            raise Exception(
                "Fix server type to be one of: 'cpu-gpu', 'cpu-only', or 'gpu-only'"
            )

        # admin only dev profile (only useful on servers with GPUs)
        if self.user.admin and server_type != "cpu-only":
            self.profile_list.extend(dev_profile(CONFIG, server_type=server_type))

        # Let KubeSpawner inspect profile_list and decide what to return.
        # ref: https://github.com/jupyterhub/kubespawner/blob/37a80abb0a6c826e5c118a068fa1cf2725738038/kubespawner/spawner.py#L1885-L1935
        return self._options_form_default()

    return dynamic_options_form
