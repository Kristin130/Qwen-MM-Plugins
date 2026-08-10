# omni-av

`qwen-mm-plugins-omni-av` exposes Qwen-Omni audio/video understanding as focused MCP tools. It can
transcribe speech, follow a clip over time, locate or count events, and describe a music track. The
audio/video tools reason over sampled frames and the embedded audio together; the ASR tools extract
and send only the audio track.

Use this capability for individual clips. For whole-video QA over videos around 30 minutes or longer,
use [`video-memory`](../video-memory/usage.md) instead.

---

## Tools

| Tool | Use it for | Main output |
|------|------------|-------------|
| `omni_asr` | Plain speech transcription without timing | One continuous text transcript |
| `omni_asr_timestamped` | Sentence- or word-level controllable ASR | Timestamped JSON segments and SRT |
| `omni_multi_speaker_asr` | Speaker diarization — who said what and when | Speaker-labelled segments and SRT |
| `omni_av_caption` | Describe what happens throughout a clip | Time spans with a description per span |
| `omni_av_grounding` | Find **when** a natural-language event appears | Matching start/end times |
| `omni_av_counting` | Count an event, object, or action | Total count and occurrence timestamps |
| `omni_music_caption` | Analyze a complete music track | Structured music tags and a dense English caption |

Every tool accepts a local `file_path` or an HTTP(S)/OSS URL and supports `dry_run=true` to preview
the model request without calling the API. The video tools also accept `fps` and `max_pixels`: raise
them only when finer temporal or visual detail is worth the extra latency and token cost.

`omni_av_grounding` is temporal — it answers **when** something happens. Core's `grounding` tool is
spatial — it answers **where** something is inside a still image.

---

## Install

The guided installer is the easiest option:

```bash
bash install.sh install
```

Or install the capability directly through a plugin marketplace:

```bash
claude plugin marketplace add https://github.com/QwenLM/Qwen-MM-Plugins.git
claude plugin install qwen-mm-plugins-core@qwen-mm-plugins
claude plugin install qwen-mm-plugins-omni-av@qwen-mm-plugins
```

The MCP server can also be launched directly from the source checkout:

```bash
uv run --extra omni-av qwen-mm-plugins-omni-av
```

---

## Requirements and configuration

| Requirement | Description |
|-------------|-------------|
| `DASHSCOPE_API_KEY` | Required — authenticates all Qwen-Omni requests. |
| `DASHSCOPE_BASE_URL` | Optional — overrides the OpenAI-compatible endpoint for a proxy or gateway. |
| `ffmpeg` + `ffprobe` | Required for local media inspection, audio extraction, transcoding, and frame fallback. |
| `OSS_AK`, `OSS_SK`, `OSS_ENDPOINT`, `OSS_BUCKET` | Optional — upload oversized local video instead of splitting it into frames and audio. Install the `oss` extra as well. |

Set variables in the environment or `~/.qwen-mm-plugins/config`. The guided installer can write the
shared configuration and verify the system dependencies:

```bash
bash install.sh configure
bash install.sh verify
```

The default model is `qwen3.5-omni-plus`; pass `model` to an individual tool to override it.

---

## Local media delivery

The endpoint limits one inline media item to 10 MB of base64 data. The tools handle that limit
automatically:

- An audio file that already fits is sent unchanged. Otherwise it is extracted/downmixed to 16 kHz
  mono and, when necessary, encoded as a duration-fitted MP3.
- A short local video is resized and transcoded to fit. At the default 1 fps / roughly 448² sampling,
  this is suitable for clips of several minutes.
- A larger video is uploaded when OSS is fully configured. Without OSS, it falls back to sampled
  frames plus the complete audio track and thins the frames until the request fits.
- An HTTP(S)/OSS URL is fetched server-side and skips the local inline upload path.

For maximum fidelity on a long input, pass a reachable URL, trim the relevant clip first, or switch
to `video-memory` for long-form QA.

---

## Example requests

```text
@meeting.mp4
Transcribe this meeting with speaker labels and sentence-level timestamps. Return SRT.

@demo.mp4
Describe the clip over time, then locate every segment where the presenter opens the settings panel.

@workout.mp4
Count every completed push-up and list the timestamp of each repetition.

@track.wav
Analyze the genre, moods, instruments, key, time signature, and vocal profile. Also write a compact
English caption that could be used as a music-generation prompt.
```

The tools work the same in Chinese — the prompt language mainly steers the wording of the answer:

```text
@会议录音.m4a
把这段录音转成文字，不需要时间戳。

@访谈.mp4
区分说话人并逐句标注时间，输出 SRT 字幕。

@产品演示.mp4
按时间顺序描述视频内容，并找出讲解人第一次展示价格页面的时间段。

@监控.mp4
数一下画面里一共出现了几辆电动车，并列出每次出现的时间点。

@片头音乐.mp3
分析这首曲子的风格、情绪、乐器、调性和节拍，再写一段可用于音乐生成的英文提示词。
```

---

## Cases

No case recorded yet. Add one in either style — see [core](../core/usage.md) for worked examples:

- **Trace** — a full session rendered to a self-contained HTML page, linked by URL.
- **Result** — the query plus a public link to the produced artifact and/or a preview screenshot.
