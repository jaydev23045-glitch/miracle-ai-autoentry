import os
import json

settings_file = "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/backend/settings.json"
if os.path.exists(settings_file):
    with open(settings_file) as f:
        s = json.load(f)
        print("Settings:", s)
        base = s.get("miracle_base_path")
        if base and os.path.exists(base):
            print("Clients in base path:", os.listdir(base))
