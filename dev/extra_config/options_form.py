# modified from https://github.com/neurohackademy/nh2020-jupyterhub/blob/8bc0d8304d5090d3a1e21a038a68f0a940e31809/deployments/hub-neurohackademy-org/config/prod.yaml
# ref for profile_options: https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html

def _define_images(CONFIG):
  """Define the image choices, based on CONFIG"""
  return {
    "Image": {
      "display_name": "Image",
      "choices": {
          name: {
              "display_name": name,
              "default": (name == "datascience"),
              "kubespawner_override": {"image": url},
          } for name, url in CONFIG["images"].items()
      },
      "unlisted_choice": {
        "enabled": True,
        "display_name": "Enter custom image",
        "display_name_in_choices": "other - select to provide a custom image",
        "validation_regex": '^.+/.+:.+$',
        "validation_message": 'Must be an image matching <user>/<name>:<tag>',
        "kubespawner_override": {
          "image": "{value}",
          "start_timeout": 600, # increase timeout to allow new images to be pulled
        },
      },
    }
  }
    
def _define_num_gpus(CONFIG):
  """Define choices for number of gpus, based on CONFIG"""
  return {
    "GPUNum": {
      "display_name": "Number of GPUs",
      "choices": {
        str(i): {
          "display_name": str(i),
          # config required to enable gpu: https://discourse.jupyter.org/t/set-runtimeclassname-for-gpu-enabled-images/21617/5
          "kubespawner_override": {
            "extra_resource_limits": {"nvidia.com/gpu": i},
            "extra_pod_config": {"runtimeClassName": "nvidia"},
          } if i > 0 else {},
        } for i in CONFIG["gpu_counts"]
      },
    }
  }
    
def _define_gpu_nodes(CONFIG):
  """Define node choices, based on CONFIG"""
  return {
    "Node": {
      "display_name": "Node",
      "choices": {
        str(node["node"]): { 
          "display_name": str(node["node"]),
          "kubespawner_override": {
              "node_selector": {"kubernetes.io/hostname": str(node["node"])},
          },
        }
        for node in CONFIG["node_info"] 
      },
    }
  }

def dynamic_options_form_withconfig(CONFIG):
  def dynamic_options_form(self):
    
    # For default server -> CPU profiles
    if not self.name:
      self.profile_list = [
        {
          "display_name": "CPU Server",
          "description": (
            "Choose your image."
            "<ul>"
            "<li><b>datascience</b>: default data analysis environment (including interpreters for Python and R)</li>"
            "<li><b>deeplearning</b>: extends datascience environment to include ML libraries (including torch, deepspeed, and 🤗)</li>"
            "</ul>"
          ),
          "profile_options": {
            **_define_images(CONFIG),
          },
          "kubespawner_override": {
            "node_selector": {"node_profile": "cpu"},
          }
        }
      ]
    
    # For named server(s) -> GPU profiles
    else:
      # add inference gpus for all users on named servers
      self.profile_list = [
        {
          "display_name": "GPU Server",
          "description": (
            "Choose your image."
            "<ul>"
            "<li><b>datascience</b>: default data analysis environment (including interpreters for Python and R)</li>"
            "<li><b>deeplearning</b>: extends datascience environment to include ML libraries (including torch, deepspeed, and 🤗)</li>"
            "</ul>"
            "Reference the GPU availability below to select your node and number of GPUs."
          ),
          "profile_options": {
            **_define_images(CONFIG),
            **_define_gpu_nodes(CONFIG),
            **_define_num_gpus(CONFIG),
          },
        }
      ]

    # Let KubeSpawner inspect profile_list and decide what to return.
    # ref: https://github.com/jupyterhub/kubespawner/blob/37a80abb0a6c826e5c118a068fa1cf2725738038/kubespawner/spawner.py#L1885-L1935
    return self._options_form_default()

  return dynamic_options_form