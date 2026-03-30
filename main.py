import json


# story is a dict obtained from a json file containing the simulation window and events
# systems is an array containing all the pv systems configs

story=json.load("data/settings.json")
systems=json.load("data/modules.json")