# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Constants for the ibaby integration."""

from __future__ import annotations

DOMAIN = "ibaby"

MANUFACTURER = "iBaby"

# Config entry data. One entry per iBaby ACCOUNT; every PPPP camera on the
# account is a device under it (CONF_CAMERAS is the list of their identities).
# The cloud is used ONLY at setup to authenticate and enumerate cameras (and for
# the built-in music list); all live media, sensors, and control run locally
# over the P2P (PPPP) session.
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_CAMERAS = "cameras"

# Per-camera identity captured at config time so the integration can rebuild a
# pyibaby Camera without another cloud round-trip on every restart.
CONF_CAMID = "camid"
CONF_CAMNAME = "camname"
CONF_CAMTYPE = "camtype"
CONF_P2P_UID = "p2p_uid"
CONF_P2P_PROVIDER = "p2p_provider"
CONF_P2P_PASSWORD = "p2p_password"  # noqa: S105 - config key name, not a secret value

# Options (editable via the options flow).
CONF_STREAM_QUALITY = "stream_quality"  # one of pyibaby STREAM_PRESETS, or "" for camera default
CONF_ENABLE_TALK = "enable_talk"

# How often the coordinator opens a short-lived control session to read the
# environment sensors. The camera pushes a record every ~5 s while connected;
# 30 s is plenty for slow-moving nursery temp/humidity/eCO2/TVOC and keeps the
# control session (and its contention with commands) light.
DEFAULT_SCAN_INTERVAL_S = 30

# Each sensor poll waits up to this long for the camera's next pushed record
# after connecting before giving up for the cycle.
SENSOR_READ_TIMEOUT_S = 8.0

# Each poll also queries the projector/privacy state (GET_PROJECTORLAMP) on the
# same session; this is best-effort and capped shorter than the sensor read.
PROJECTOR_READ_TIMEOUT_S = 4.0

# Base TCP port for the per-camera pyibaby.rtspd subprocess. Each camera gets a
# distinct port allocated from here upward; the integration binds 127.0.0.1 only
# so the RTSP server is never exposed off-host (go2rtc pulls it locally).
RTSP_BASE_PORT = 8554
RTSP_BIND_HOST = "127.0.0.1"

# Stop the rtspd subprocess (releasing the camera's video P2P session) after no
# consumer has requested the stream for this long, so we are not holding a live
# session 24/7.
STREAM_IDLE_STOP_S = 120

# Switches with no device read-back (the camera does not report projector/PTZ
# state, and moonlight self-disables after ~15 min), so their HA state is
# optimistic / assumed.
SWITCH_MOONLIGHT = "moonlight"
SWITCH_MUSIC_LIGHT = "music_light"
SWITCH_PRIVACY = "privacy"

# The projector lamp (moonlight / music-light) auto-disables in hardware after
# this many seconds; the switch flips itself back off in HA to match.
PROJECTOR_AUTO_OFF_S = 900

# PTZ directions exposed as button entities (values map to pyibaby protocol
# PTZ_UP/DOWN/LEFT/RIGHT). Continuous-until-stop is not assumed; these issue a
# single discrete move.
PTZ_UP = "up"
PTZ_DOWN = "down"
PTZ_LEFT = "left"
PTZ_RIGHT = "right"
