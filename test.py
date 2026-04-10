import json
from src import WeatherModel,Simulation

# story is a dict obtained from a json file containing the simulation window and events
# systems is an array containing all the pv systems configs

with open("data/settings.json") as json_file:
    story = json.load(json_file)

with open("data/modules.json") as json_file:
    systems = json.load(json_file)


wm=WeatherModel.WeatherModel()
sim=Simulation.Simulation(systems,wm,story)
sim.run()

sim.plot_id("sys1")