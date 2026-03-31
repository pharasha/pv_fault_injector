from pvlib.pvsystem import PVSystem, Array, FixedMount, retrieve_sam
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS

class PvSystem():
    """
    PvSystem Class description
    """
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
        self.strings              = config["strings"]
        self.module_cec           = config["module_cec"]
        self.inverter_cec         = config["inverter_cec"]

        #PVLIB
        self.location=Location(latitude=self.latitude, 
                               longitude=self.longitude,
                               tz=self.timezone)
        
        self.module=retrieve_sam('CECMod')[self.module_cec]

        self.inverter=retrieve_sam('cecinverter')[self.inverter_cec]

        self.array=Array(mount=FixedMount(surface_tilt=self.tilt,
                                          surface_azimuth=self.azimuth),
                         module_parameters=self.module,
                         temperature_model_parameters=PARAMS['sapm']['open_rack_glass_glass'],
                         modules_per_string=self.modules_per_string,
                         strings=self.strings_per_inverter)
        
        self.pv_sys=PVSystem(arrays=self.array,inverter_parameters=self.inverter)

        self.mc=ModelChain(system=self.pv_sys,location=self.location) #TOODO: CHECK MORE ABOUT LOSS_PARAMETERS                          


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