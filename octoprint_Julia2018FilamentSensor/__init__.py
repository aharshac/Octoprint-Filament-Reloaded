# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import Events
import RPi.GPIO as GPIO
from time import sleep
from flask import jsonify

'''
Uses Pi's internal pullups.

GPIO states
Open    - HIGH
Closed  - LOW
'''

class Julia2018FilamentSensorPlugin(octoprint.plugin.StartupPlugin,
                             octoprint.plugin.EventHandlerPlugin,
                             octoprint.plugin.TemplatePlugin,
                             octoprint.plugin.SettingsPlugin,
                             octoprint.plugin.BlueprintPlugin,
                             octoprint.plugin.AssetPlugin):

    '''
    Popup messages
    '''
    def log_info(self, txt):
        self._logger.info(txt) 

    def log_error(self, txt):
        self._logger.error(txt)

    def popup_notice(self, txt):
        self.log_info(txt)
        self._plugin_manager.send_plugin_message(self._identifier, dict(type="popup", msgType="notice", msg=str(txt)))

    def popup_success(self, txt):
        self.log_info(txt)
        self._plugin_manager.send_plugin_message(self._identifier, dict(type="popup", msgType="success", msg=str(txt)))

    def popup_error(self, txt):
        self.log_error(txt)
        self._plugin_manager.send_plugin_message(self._identifier, dict(type="popup", msgType="error", hide=False, msg=str(txt)))

    def status_dict(self):
        status = "-1"
        if self.has_pin():
            status = "0" if self.no_filament() else "1"
        status1 = "-1"
        if self.has_pin2():
            status1 = "0" if self.no_filament2() else "1"
        return dict(filament=status, filament2=status1, active_tool=self.active_tool)
    
    def send_status_to_hmi(self):
        self._plugin_manager.send_plugin_message(self._identifier, self.status_dict())

    '''
    Settings
    '''
    @property
    def enabled(self):
        return int(self._settings.get(["enabled"]))

    @property
    def pin(self):
        return int(self._settings.get(["pin"]))

    @property
    def bounce(self):
        return int(self._settings.get(["bounce"]))

    @property
    def switch(self):
        return int(self._settings.get(["switch"]))

    @property
    def gcode_pin(self):
        return str(self._settings.get(["gcode_pin"])).splitlines()

    @property
    def pin2(self):
        return int(self._settings.get(["pin2"]))

    @property
    def bounce2(self):
        return int(self._settings.get(["bounce2"]))

    @property
    def switch2(self):
        return int(self._settings.get(["switch2"]))

    @property
    def gcode_pin2(self):
        return str(self._settings.get(["gcode_pin2"])).splitlines()

    @property
    def mode(self):
        return int(self._settings.get(["mode"]))

    @property
    def pause_print(self):
        return self._settings.get_boolean(["pause_print"])

    '''
    Sensor states
    '''
    def has_pin(self):
        return self.pin != -1

    def has_pin2(self):
        return self.pin2 != -1

    def no_filament(self):
        try:
            return GPIO.input(self.pin) == self.switch
        except Exception as e:
            self.popup_error(e)
            return False
        

    def no_filament2(self):
        try:
            return GPIO.input(self.pin2) == self.switch2
        except Exception as e:
            self.popup_error(e)
            return False

    '''
    Sensor Initialization
    '''
    def _setup_sensor(self):
        try:
            if self.has_pin():
                self.log_info("Setting up sensor.")

                if self.mode == 0:
                    self.log_info("Using Board Mode")
                    GPIO.setmode(GPIO.BOARD)
                else:
                    self.log_info("Using BCM Mode")
                    GPIO.setmode(GPIO.BCM)
                
                self.log_info("Filament Sensor 1 active on GPIO Pin [%s]"%self.pin)
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

                if self.has_pin2():
                    self.log_info("Filament Sensor 2 active on GPIO Pin [%s]"%self.pin)
                    GPIO.setup(self.pin2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                else:
                    self.log_info("Pin 2 not configured, won't work unless configured!")
            else:
                self.log_info("Pin not configured, won't work unless configured!")
        except Exception as e:
            self.popup_error(e)

    '''
    Callbacks
    '''
    def on_after_startup(self):
        self.log_info("Julia 2018 Filament Sensor started")
        self._setup_sensor()

    def on_event(self, event, payload):
        if event is Events.TOOL_CHANGE:
            self.active_tool = int(payload["new"])
            self.send_status_to_hmi()

        # Early abort in case of out ot filament when start printing, as we
        # can't change with a cold nozzle
        if event is Events.PRINT_STARTED:
            if ( (self.has_pin() and self.no_filament()) or (self.has_pin2() and self.no_filament2()) ):
                self.log_error("Printing aborted: no filament detected!")
                self._printer.cancel_print()
                self.send_status_to_hmi()

        # Enable sensor
        if event in (
            Events.PRINT_STARTED,
            Events.PRINT_RESUMED
        ):
            self.log_info("%s: Enabling filament sensor." % (event))
            if self.has_pin():
                GPIO.remove_event_detect(self.pin)
                GPIO.add_event_detect(
                    self.pin, GPIO.BOTH,
                    callback=self.cb_pin,
                    bouncetime=self.bounce
                )
            if self.has_pin2():
                GPIO.remove_event_detect(self.pin2)
                GPIO.add_event_detect(
                    self.pin2, GPIO.BOTH,
                    callback=self.cb_pin2,
                    bouncetime=self.bounce2
                )
        # Disable sensor
        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR
        ):
            self.log_info("%s: Disabling filament sensor." % (event))
            GPIO.remove_event_detect(self.pin)
            GPIO.remove_event_detect(self.pin2)

    def cb_pin(self, _):
        sleep(self.bounce/1000)

        if not self.no_filament():
            return self.popup_success("Filament 1 detected!")

        self.send_status_to_hmi()
        self.popup_error("Out of filament 1!")

        if self.active_tool != 0:
            return

        if self.pause_print:
            self.log_info("Pausing print.")
            self._printer.pause_print()
        if self.gcode_pin:
            self.log_info("Sending out of filament GCODE")
            self._printer.commands(self.gcode_pin)
    
    def cb_pin2(self, _):
        sleep(self.bounce2/1000)

        if not self.no_filament2():
            return self.popup_success("Filament 2 detected!")

        self.send_status_to_hmi()
        self.popup_error("Out of filament 2!")

        if self.active_tool != 1:
            return

        if self.pause_print:
            self.log_info("Pausing print.")
            self._printer.pause_print()
        if self.gcode_pin2:
            self.log_info("Sending out of filament 2 GCODE")
            self._printer.commands(self.gcode_pin2)

    '''
    REST status
    '''
    @octoprint.plugin.BlueprintPlugin.route("/status", methods=["GET"])
    def check_status(self):
        # status = "-1"
        # if self.has_pin():
        #     status = "0" if self.no_filament() else "1"
        # status1 = "-1"
        # if self.has_pin2():
        #     status1 = "0" if self.no_filament2() else "1"
        # return jsonify(filament=status, filament2=status1)
        self.send_status_to_hmi()
        return jsonify(self.status_dict())

    '''
    Update Management
    '''
    def get_update_information(self):
        return dict(
            octoprint_filament=dict(
                displayName="Julia 2018 Filament Sensor",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="aharshac",
                repo="Julia2018FilamentSensor",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/aharshac/OctoPrint-Julia2018FilamentSensor/archive/{target_version}.zip"
            )
        )

    '''
    Plugin Management
    '''
    def initialize(self):
        self.log_info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
        if GPIO.VERSION < "0.6":       # Need at least 0.6 for edge detection
            raise Exception("RPi.GPIO must be greater than 0.6")
        GPIO.setwarnings(False)        # Disable GPIO warnings
        self.active_tool = 0
        self.send_status_to_hmi()
    
    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.popup_success('Settings saved!')
        self._setup_sensor()

    def get_assets(self):
        return dict(js=["js/Julia2018FilamentSensor.js"])
 
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    def get_settings_defaults(self):
        return dict(
            enabled = True,
            pin     = -1,   # Default is no pin
            bounce  = 250,  # Debounce 250ms
            switch  = 0,    # Normally Open
            gcode_pin = '',
            pin2     = -1,   # Default is no pin
            bounce2  = 250,  # Debounce 250ms
            switch2  = 0,    # Normally Open
            gcode_pin2 = '',
            mode    = 0,    # Board Mode
            pause_print = True,
        )

__plugin_name__ = "Julia 2018 Filament Sensor"
__plugin_version__ = "1.0.0"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Julia2018FilamentSensorPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}
