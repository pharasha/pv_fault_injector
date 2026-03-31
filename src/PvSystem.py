from pvlib.pvsystem import PVSystem, Array, FixedMount, retrieve_sam
from pvlib.location import Location
from pvlib.modelchain import ModelChain

class PvSystem:
    def __init__(self, config):
        self.id                   = config["id"]
        self.latitude             = config["latitude"]
        self.longitude            = config["longitude"]
        self.altitude             = config["altitude_m"]
        self.timezone             = config["timezone"]
        self.tilt                 = config["tilt_deg"]
        self.azimuth              = config["azimuth_deg"]
        self.loss                 = config["system_loss_fraction"]
        self.modules_per_string   = config["modules_per_string"]
        self.strings_per_inverter = config["strings_per_inverter"]
        self.module_cec           = config["module_cec"]
        self.inverter_cec         = config["inverter_cec"]

    def build_system(self, module_params=None):
        # module_params: override parameters used by fault injection (degradation, PID, etc.)
        pass

    def location(self):
        pass

    def simulate(self, weather_df, module_params=None):
        pass

    def simulate_chunked(self, chunks):
        # chunks: list of (weather_df, module_params) from degradation_timeseries()
        pass