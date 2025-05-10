from importlib import import_module

panel_module = import_module('.panel', package=__name__)
MainPanel = panel_module.MainPanel

classes = [MainPanel] 