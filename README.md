# iBaby Monitor (Home Assistant)

A Home Assistant custom integration for iBaby M7 / M7T baby monitors. It talks to
the camera locally over its native P2P (PPPP/PPCS) protocol - the same protocol
the official app uses - via the [`pyibaby`](https://gitlab.com/ggiesen/pyibaby)
library. The iBaby cloud is contacted only at setup, to log in and enumerate the
cameras on your account (and to fetch the built-in music list); all live video,
audio, sensors, and control run on your LAN with no cloud in the path.

> This repo is developed on
> [GitLab](https://gitlab.com/ggiesen/ha-ibaby) and mirrored to
> [GitHub](https://github.com/ggiesen/ha-ibaby) for HACS. File issues on
> [GitLab](https://gitlab.com/ggiesen/ha-ibaby/-/issues).

## Features

- **Camera** - live 1080p H.264 + audio, served through Home Assistant's bundled
  go2rtc (WebRTC / HLS), with snapshots.
- **Two-way audio (talk-back)** - speak to the room through the camera (see the
  caveats below; this is the most setup-sensitive feature).
- **Environment sensors** - temperature, humidity, eCO2, and TVOC, pushed by the
  camera roughly every 5 seconds.
- **Pan / tilt** - up / down / left / right as button entities.
- **Music** - play the built-in lullabies / songs / nature / stories / white
  noise as a `media_player`, with media browsing.
- **Lights / privacy** - moonlight, music-light, and privacy mode as switches.

## Requirements

- Home Assistant OS (HAOS) or Supervised, with the bundled **go2rtc** (HA
  2024.11+). The integration hands go2rtc a local RTSP URL it produces itself,
  because the HAOS-bundled go2rtc cannot exec arbitrary programs.
- An iBaby account (email + password) with at least one M7 / M7T camera.
- The cameras must be reachable on the same L2 network as Home Assistant (the
  integration discovers them by LAN broadcast).

## Installation

### HACS (recommended)

1. In HACS, add this repository as a custom repository (category: *Integration*):
   `https://github.com/ggiesen/ha-ibaby`.
2. Install **iBaby Monitor**, then restart Home Assistant.
3. Go to *Settings -> Devices & Services -> Add Integration -> iBaby Monitor* and
   sign in with your iBaby email and password.

### Manual

Copy `custom_components/ibaby/` into your Home Assistant `config/custom_components/`
directory and restart.

## How the video path works

The HAOS-bundled go2rtc is locked to `exec: allow_paths: [ffmpeg]`, so it cannot
run a Python producer directly. Instead the integration starts a small
`pyibaby.rtspd` subprocess per camera that holds one P2P session and serves it as
`rtsp://127.0.0.1:<port>/cam`; the camera entity hands that URL to go2rtc, which
ingests it and fans it out to WebRTC / HLS consumers. The control and sensor path
uses a second, lightweight P2P session, so video and control run side by side.

## Two-way audio caveats

Talk-back rides go2rtc's WebRTC audio backchannel (PCMU, which the camera speaks
natively). It requires Home Assistant to be served over **HTTPS** (browsers block
microphone access otherwise) and a camera card that exposes a microphone button.
Treat it as experimental and expect to test it in a desktop browser first.

## Branching

`master` is the primary branch.

## Licence

[MPL-2.0](LICENSE).
