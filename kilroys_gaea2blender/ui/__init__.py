from importlib import import_module, reload as _reload

panel_module = import_module('.panel', package=__name__)
_reload(panel_module)
MainPanel = panel_module.MainPanel

classes = [MainPanel] 