# Web stub（国内播放：站内跳秒 + R2/本地 64 kbps 音频）

完整 React 播放器见 ARCHITECTURE.md §8.4；本目录是**最小可播 stub**，用于验证：

- cite 主链接：`/watch/{video_id}?t=<秒>`
- 播放地址：`GET /api/play-url/{video_id}` → LocalStorage `data/r2-mirror/play/{id}.m4a` 或 R2 签名 stub
- Range 拉流：`GET /api/media/{video_id}`（本地文件；生产可换 Worker/CDN）

## 跑起来

```bash
# 需已有 play 音频（流水线 s02 写入 data/r2-mirror/play/<id>.m4a）
cd /workspace/tcm-video-kb
.venv/bin/python web/stub_server.py --port 8765
# 浏览器打开 http://127.0.0.1:8765/watch/shl-001?t=125
```

真实 R2：在 `configs/.env` 填 `R2_*`（见 `configs/.env.example`）。
播放 stub HMAC 请设 `TCMKB_MEDIA_HMAC_SECRET`（勿直接复用 `R2_SECRET_ACCESS_KEY`）。
未配置 R2 时走本地 mirror。
版权：个人/内部学习；优先私有桶 + 签名 URL，勿把桶设为 public。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/watch/{video_id}?t=&end=` | 极简 HTML：`<audio>` + `currentTime = t` |
| GET | `/api/play-url/{video_id}` | JSON：`{url,key,mode,expires_s}` |
| GET | `/api/media/{video_id}` | 本地 m4a，支持 `Range` |

签名 stub（`mode=r2-presign-stub`）的 `token`/`exp` 由 `tcmkb_core.play.verify_media_token` 校验；上线再换成 boto3 `generate_presigned_url`。
