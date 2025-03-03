# modified from https://github.com/neurohackademy/nh2020-jupyterhub/blob/8bc0d8304d5090d3a1e21a038a68f0a940e31809/deployments/hub-neurohackademy-org/config/prod.yaml
# ref for profile_options: https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html

def _define_images(images):
  """Define the image choices"""
  return {
    "Image": {
      "display_name": "Image",
      "choices": {
          name: {
              "display_name": name,
              "default": (name == "datascience"),
              "kubespawner_override": {"image": url},
          } for name, url in images.items()
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
    
def _define_num_gpus(gpu_counts):
  """Define choices for number of gpus"""
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
        } for i in gpu_counts
      },
    }
  }
    
def _define_gpu_nodes(node_info):
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
        for node in node_info
      },
    }
  }

# image descriptions
image_des = """Choose your image.
                <ul>
                <li><b>datascience</b>: default data analysis environment (including interpreters for Python and R)</li>
                <li><b>deeplearning</b>: extends datascience environment to include ML libraries (including torch, deepspeed, and 🤗)</li>
                </ul>
            """

# define CPU profile
def cpu_profile(CONFIG):
  return [{
    "display_name": "CPU Server",
    "description": image_des,
    "profile_options": {
      **_define_images(CONFIG["images"]),
    },
    "kubespawner_override": {
      "node_selector": {"node_profile": "cpu"},
    }
  }]

# define GPU profile
def gpu_profile(CONFIG):
  return [{
    "display_name": "GPU Server",
    "description": image_des + "Reference the GPU availability below to select your node and number of GPUs.",
    "profile_options": {
      **_define_images(CONFIG["images"]),
      **_define_gpu_nodes(CONFIG["node_info"]),
      **_define_num_gpus(CONFIG["gpu_counts"]),
    },
  }]

# define volume access profile - for accessing workspace volume
# has low resources and no gpus
def volume_profile(CONFIG):
  return [{
    "display_name": "Volume Access",
    "description": "Use this profile to access the workspace volume.",
    "profile_options": {
      **_define_images(CONFIG["images"]),
    },
    "kubespawner_override": {
      "cpu_guarantee": 1,
      "cpu_limit": 12,
      "mem_guarantee": "1G",
      "mem_limit": "12G"
    },
  }]

# define dev profile
# def dev_profile(CONFIG):
#   return [{
#     "display_name": "Dev (admin only)",
#     "description": "Set custom images, resources, etc for testing",
#     "profile_options": {
#       **_define_images(CONFIG),
#       **_define_gpu_nodes(CONFIG),
#       **_define_num_gpus(CONFIG),
#     },
#   }]

# return profile options based on the server type and config provided 
def dynamic_options_form_withconfig(CONFIG):
  def dynamic_options_form(self):
    
    server_type = CONFIG['server_type']
    
    if server_type == 'cpu-gpu': # For default server -> CPU profiles, for named servers -> GPU profiles
      self.profile_list = cpu_profile(CONFIG) if not self.name else gpu_profile(CONFIG)
    
    elif server_type == 'cpu-only':
      self.profile_list = cpu_profile(CONFIG)
    
    elif server_type == 'gpu-only':  
      self.profile_list = gpu_profile(CONFIG) + volume_profile(CONFIG)
    
    else:
      raise Exception("Fix server type to be one of: 'cpu-gpu', 'cpu-only', or 'gpu-only'")
    

    # Let KubeSpawner inspect profile_list and decide what to return.
    # ref: https://github.com/jupyterhub/kubespawner/blob/37a80abb0a6c826e5c118a068fa1cf2725738038/kubespawner/spawner.py#L1885-L1935
    return self._options_form_default()

  return dynamic_options_form