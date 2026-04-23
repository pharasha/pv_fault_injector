from pvlib.pvsystem import PVSystem, Array, FixedMount, retrieve_sam
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS

class PvSystem():
    """
    PvSystem Class description
    """
    def __init__(self, config):
        self.latitude             = config["latitude"]
        self.longitude            = config["longitude"]
        self.altitude             = config["altitude_m"]
        self.timezone             = config.get("timezone", "Europe/Zurich")
        self.tilt                 = config["tilt_deg"]
        self.azimuth              = config["azimuth_deg"]
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
                         strings=self.strings)
        
        self.pv_sys=PVSystem(arrays=[self.array],inverter_parameters=self.inverter)

        self.mc=ModelChain(system=self.pv_sys,location=self.location, spectral_model='no_loss',aoi_model='physical') #TOODO: CHECK MORE ABOUT LOSS_PARAMETERS  

    def run_model(self,weather):
        self.mc.run_model(weather)  
        return self.mc.results                         