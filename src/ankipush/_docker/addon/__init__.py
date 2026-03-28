from aqt import mw, gui_hooks
from . import logic

gui_hooks.profile_did_open.append(lambda: logic.run(mw))
