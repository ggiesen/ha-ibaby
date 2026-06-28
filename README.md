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
  noise as a `media_player`, with media browsing and volume control.
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

## Two-way audio (talk-back)

Talk-back rides go2rtc's WebRTC audio backchannel. The camera speaks G.711 A-law
(PCMA) natively, and the `pyibaby.rtspd` bridge advertises an ONVIF backchannel
on its local RTSP stream, so go2rtc negotiates the return audio path
automatically - nothing to configure on the integration side.

Two things are outside the integration's control and you have to set them up:

- **HTTPS.** Browsers only grant microphone access on a secure origin, so Home
  Assistant must be reached over `https://` (your own TLS, or Nabu Casa Cloud).
- **A card with a microphone.** Home Assistant's built-in camera/WebRTC card does
  not capture the microphone yet (native two-way audio is still unmerged upstream
  as of mid-2026). Use a WebRTC card that does, such as the
  [Advanced Camera Card](https://card.camera/) or
  [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC), set to include the
  microphone (for example `media: video,audio,microphone`). Press its
  talk/microphone button and speak; it plays out of the camera.

Treat it as experimental and test in a desktop browser first. When native
two-way audio lands in Home Assistant it should work through the standard card
with no change here.

## Branching

`master` is the primary branch.

## Licence

[MPL-2.0](LICENSE).
