# Lab 13 — 本地录音、转写、摘要与 RAG

这个实验把语音接入已有知识平台：**录音 → 转写 → 人工核对 → 摘要 → 文档 → 检索**。
无需云 API key。语音识别使用 faster-whisper；摘要使用本地 Ollama。

## 1. 启动

在 `starter_repo` 执行：

```sh
.venv/bin/python -m pip install -e '.[voice]'
.venv/bin/python scripts/setup_voice.py
ollama pull qwen2.5:3b
sh scripts/start_local.sh
```

如果 API 已经运行，代码更新后在 Server status 停止再启动一次。
语音模型下载后只需点击 Check setup，模型首次转写时加载；不需要为模型文件重启。
默认的 Whisper base 为多语言模型，CPU int8 运行。summary 默认选较小的 qwen2.5:3b；
这是一项本地资源取舍，并不声称它是最新或最强模型。

模型下载需要网络；录音不上传到模型下载站。官方站点不可达时，
可以自行指定信任的镜像，例如在本机验证可达后使用：

```sh
HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 .venv/bin/python scripts/setup_voice.py
```

只在下载命令设置该变量，不修改全局 Docker registry 或运行时模型地址。

## 2. 页面操作

打开 [Voice notes](http://127.0.0.1:8000/#voice)：

1. Check setup 应显示 speech 和 summary 均可用。
2. 选择中文、English 或自动检测；短录音明确选语言通常更容易判断效果。
3. 点击 **Start recording**，在浏览器允许麦克风。观察录音状态与音量条。
4. 每约 8 秒提交一个完整 WAV；转写会在该 chunk 处理完后出现。
5. 点击 **Stop recording**。尾段也会提交，麦克风会关闭。
6. 默认在队列完成后生成摘要；可取消自动摘要，先修正 transcript，再点 Generate summary。
7. 检查专有名词、金额、日期、决定与行动项。可以编辑原文和摘要。
8. 填标题，**Save to document library**。随后选择 **Index for RAG**。
9. 在 RAG answers 中按 source `voice-notes` 查询，核对引用文档。

支持导入/拖入浏览器可解码的音频，最多 20 MiB / 10 分钟。
嵌入式浏览器若没有麦克风支持，用 Chrome/Safari 打开同一 localhost 页面，或导入音频。
这不是云端浏览器 SpeechRecognition 服务。

原始音频在页面内存中。Download audio 保存 WAV 到自己的电脑；刷新会丢失未下载音频。
后端不归档音频；只有明确保存的 transcript/summary 才写入知识库。
离开 Voice notes 会停止麦克风并完成排队的请求。完整离开页面前仍应保存/下载。

## 3. 读代码顺序

| 文件 | 职责 |
|---|---|
| `app/static/voice-worklet.js` | 音频线程采集 PCM；停止时 flush 最后一段 |
| `app/static/voice.js` | WAV 编码、顺序上传、重试、编辑、下载、保存/索引 |
| `app/api/voice.py` | `/voice/status`、`/voice/transcribe`、`/voice/summary` |
| `app/dto/voice.py` | transcript、结构化摘要、行动项等传输类型 |
| `app/services/voice.py` | 本地模型加载、静音过滤、转写、分段摘要与合并 |
| `scripts/setup_voice.py` | 显式下载权重并验证本地加载 |

处理链：

```text
getUserMedia → AudioWorklet → PCM WAV → POST /voice/transcribe
 → 本地 Whisper + VAD → 可编辑 transcript
 → POST /voice/summary → 本地 Ollama + JSON schema + Pydantic
 → 可编辑 summary → POST /documents → 可选 POST /rag/documents/{id}/index
```

ASR 在 worker thread 运行，不阻塞 FastAPI 的事件循环。
一次只处理一个模型转写；页面按顺序发送 chunk。实时录音队列积压到 8 段时停止采集，
保留音频并完成转写。请求失败保留队首 chunk，用户可重试，不偷偷跳过。
输入音频只接受单声道 16-bit PCM WAV，8–48 kHz，每请求最多 30 秒 / 3 MiB。
浏览器负责把导入音频解码并切成相同格式。

摘要最多接受 24,000 字符。长文本按约 3,000 字符分段，再两两合并摘要。
这限制上下文长度，但摘要压缩仍会损失信息；原始转写保留供检查。
提示词把 transcript 当作数据；它没有权限调用工具或创建 follow-up。
行动项未说出负责人/日期时返回 null。Pydantic 验证结构，不验证事实。
行动项还必须附一段可在 transcript 中找到的原文：没有匹配引用的行动项会移除，
不在这段引用中的负责人或日期会清空，并在页面提醒复核。
这个检查防止把“周五”擅自变成某个日历日期，但仍不能证明任务语义或整段摘要正确。

## 4. 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `VOICE_ENABLED` | `true` | 可设 false 关闭语音处理；缺少可选依赖不影响其他页面启动 |
| `VOICE_MODEL_PATH` | `var/models/whisper-base` | 仅从本地目录加载，不在录音请求内下载 |
| `VOICE_SUMMARY_MODEL` | `qwen2.5:3b` | 改为已在本机 Ollama 下载的 chat model |
| `VOICE_OLLAMA_URL` | `http://127.0.0.1:11434` | 仅接受 loopback 主机，保持此功能的本地处理边界 |

想试 small：先 `scripts/setup_voice.py --model small --output var/models/whisper-small`，
再用 `VOICE_MODEL_PATH=var/models/whisper-small` 启动。模型越大不保证在这台机器上实时。
ASR 和摘要不要求 RAG_ENABLED；索引和检索仍需 RAG 的 Ollama embedding/Qdrant/ES。
认证启用时，语音 API 沿用身份认证，保存文档仍需要 editor/admin 权限。

## 5. 验收练习与边界

- 说一句含名字与数字的话，停止在半个 chunk 内，确认最后几个字没有丢失。
- 静音录制后停止：不要凭空出现会议内容。
- 输入“李明周五检查检索报告；是否换模型下周再决定”，核对决定与未决事项。
- 模型不可用时查看明确错误；转写失败后重试，确认没有重复追加已成功的 chunk。
- 保存后查询原文，确认 API → PostgreSQL → ES，以及显式 RAG 索引的边界。

这是 **near-real-time 分段转写**，不是逐词 streaming ASR。延迟为采集窗口 + 排队 + 推理；
不同 chunk 的语言自动检测可能不同，跨边界句子也可能不完整。
目前没有 diarization（说话人分离）、会议自动加入、后台录音归档或跨刷新恢复。
摘要是待核对的草稿，不会自动发布为已审批知识。

2026-10-25 本机验收：用系统生成的英语音频验证了实际 Whisper 转写、静音不出字、
错误 WAV/空摘要输入校验、页面音频导入、摘要、文档保存与 RAG 索引。
浏览器使用合成音源验证了边录边转写、停止时尾段提交和麦克风 track 释放；
没有替用户开启或录制真实麦克风。实际麦克风权限仍需用户首次点击时允许。

复核日期 2026-10-25。资料：[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)、
[getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)、
[AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)。
