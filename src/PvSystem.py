import pvlib as pvl

class PvSystem:
    def __init__(self, config):
        self.id=config["id"]
        self.latitude=config["latitude"]
        self.longitude=config["longitude"]
        self.peakPower=config["peakPower"]