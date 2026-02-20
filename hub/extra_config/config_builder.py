import os
import yaml
from options_form import dynamic_options_form_withconfig
from prespawn_hook import set_spawner_resources

# get cluster from env variable
CLUSTER = os.environ.get("JUPYTERHUB_CLUSTER")

# load config yamls
with open("/etc/jupyterhub/config/clusters.yaml") as f:
    cluster = yaml.safe_load(f)[CLUSTER]
with open("/etc/jupyterhub/config/users.yaml") as f:
    users = yaml.safe_load(f)

# setup config
CONFIG = {
    "server_type": cluster["server_type"],
    "named_server_limits": cluster.get("named_server_limits", {}),
    "gpu_counts": cluster.get("num_gpus_allowed", []),
    "node_info": cluster.get("gpu_nodes", []),
    "status_urls": cluster.get("status_urls", {}),
    "users": users,
    "user_roles": {
        user: role
        for role, userlist in users.items()
        for user in userlist
    },
}


# update config with image info
def update_config(profile_list=None):
    # add images if profile list is provided
    if profile_list is not None:
        CONFIG["images"] = {
            p["display_name"]: p["kubespawner_override"]["image"]
            for p in profile_list
        }
    return CONFIG
