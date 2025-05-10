from importlib import import_module

classes = []

for mod_name in ('.globe', '.landscape'):
    try:
        m = import_module(mod_name, package=__name__)
        if hasattr(m, 'classes'):
            classes.extend(m.classes)
    except ModuleNotFoundError:
        continue

# sub-modules will append to this list when they are imported 