-- StudyFloat: minimal OSC styling for the floating video window.
-- Borderless window dragging is handled natively by mpv's --window-dragging=yes,
-- so no custom drag logic is needed here.
local mp = require 'mp'

-- OSC in "auto" mode: appears on mouse move, hides after ~2 seconds.
mp.set_property('osc', 'yes')
mp.set_property(
  'script-opts',
  'osc-visibility=auto,osc-hidetimeout=2000,osc-layout=bottombar,osc-timetotal=no,osc-fontsize=12'
)
