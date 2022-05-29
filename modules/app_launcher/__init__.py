import tidal
import tidal_helpers
from app import MenuApp
from scheduler import get_scheduler
import lodepng
import emf_png
import term
import sys
import ujson
import os
import functools

SPLASHSCREEN_TIME = 300 # ms

class Launcher(MenuApp):

    APP_ID = "menu"
    TITLE = "EMF 2022 - TiDAL\nBoot Menu"

    def loadInfo(self, folder, name):
        try:
            info_file = "{}/{}/metadata.json".format(folder, name)
            with open(info_file) as f:
                information = f.read()
            return ujson.loads(information)
        except BaseException as e:
            return {}

    def list_user_apps(self):
        apps = []
        for folder in sys.path:
            try:
                files = os.listdir(folder)
            except OSError:
                files = []
            for name in files:
                components = [part for part in folder.split("/") if part] + [name]
                app = {
                    "path": ".".join(components),
                    "callable": "main",
                    "name": name,
                    "icon": None,
                    "category": "unknown",
                    "hidden": False,
                }
                metadata = self.loadInfo(folder, name)
                if metadata:
                    app.update(metadata)
                    if not app["hidden"]:
                        apps.append(app)
        return apps

    def list_core_apps(self):
        core_app_info = [
            ("USB Keyboard", "hid", "USBKeyboard"),
            ("Name Badge", "hello", "Hello"),
            ("Torch", "torch", "Torch"),
            ("Logo", "emflogo", "EMFLogo"),
            ("Update Firmware", "otaupdate", "OtaUpdate"),
            ("Wi-Fi Connect", "wifi_client", "WifiClient"),
            ("Sponsors", "sponsors", "Sponsors"),
            ("Battery", "battery", "Battery"),
            ("Accelerometer", "accel_app", "Accel"),
            ("Settings", "settings_app", "SettingsApp"),
            # ("Swatch", "swatch", "Swatch"),
            ("uGUI Demo", "ugui_demo", "uGUIDemo")
        ]
        core_apps = []
        for core_app in core_app_info:
            core_apps.append({
                "path": core_app[1],
                "callable": core_app[2],
                "name": core_app[0],
                "icon": None,
                "category": "unknown",
            })
        return core_apps

    @property
    def choices(self):
        # Note, the text for each choice needs to be <= 16 characters in order to fit on screen
        apps = self.list_core_apps() + self.list_user_apps()
        choices = []
        for app in apps:
            choices.append((app['name'], functools.partial(self.launch, app['path'], app['callable'])))
        return choices

    # Boot entry point
    def main(self):
        get_scheduler().main(self)

    def as_terminal_app(self):
        while True:
            term.clear()
            choice = term.menu(
                self.window.title.replace("\n", " "),
                [text for (text, cb) in self.choices]
            )
            self.choices[choice][1]()

    def __init__(self):
        super().__init__()
        self._apps = {}
        self.show_splash = True

    def on_start(self):
        super().on_start()
        self.window.set_choices(self.choices, redraw=False)
        self.buttons.on_up_down(tidal.CHARGE_DET, self.charge_state_changed)
        self.buttons.on_press(tidal.BUTTON_FRONT, lambda: self.update_title(redraw=True))

        initial_item = 0
        try:
            with open("/lastapplaunch.txt") as f:
                initial_item = int(f.read())
        except:
            pass
        self.window.set_focus_idx(initial_item, redraw=False)

    def on_activate(self):
        if self.show_splash and SPLASHSCREEN_TIME:
            # Don't call super, we don't want MenuApp to call cls yet
            self.buttons.deactivate() # Don't respond to buttons until after splashscreen dismissed
            (w, h, buf) = lodepng.decode565(emf_png.DATA)
            tidal.display.blit_buffer(buf, 0, 0, w, h)
            self.after(SPLASHSCREEN_TIME, lambda: self.dismiss_splash())
        else:
            self.update_title(redraw=False)
            super().on_activate()

    def dismiss_splash(self):
        self.show_splash = False
        self.on_activate()

    def update_title(self, redraw):
        title = self.TITLE
        if not get_scheduler().is_sleep_enabled():
            title += "\nSLEEP DISABLED"
        pwr = tidal.CHARGE_DET.value() == 0 and 1 or 0
        conn = tidal_helpers.usb_connected() and 1 or 0
        if pwr or conn:
            title += f"\nUSB pwr={pwr} conn={conn}"
        if title != self.window.title:
            self.window.set_title(title, redraw=redraw)

    def launch(self, module_name, app_name):
        app = self._apps.get(app_name)
        if app is None:
            print(f"Creating app {app_name}...")
            module = __import__(module_name)
            app = getattr(module, app_name)()
            self._apps[app_name] = app
        with open("/lastapplaunch.txt", "w") as f:
            f.write(str(self.window.focus_idx()))
        get_scheduler().switch_app(app)

    def charge_state_changed(self, charging):
        if not self.show_splash:
            self.update_title(redraw=True)
        get_scheduler().usb_plug_event(charging)
