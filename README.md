# SynthID 本地 Web 服务

基于 [remove-ai-watermarks](https://github.com/wiltodelta/remove-ai-watermarks) 的简易本地 Web 服务，上传图片后通过 SDXL 扩散模型去除 SynthID 隐藏水印。

## 前置要求

- Python 3.10+
- Apple Silicon Mac（MPS）或 NVIDIA GPU（CUDA）
- 约 8 GB 可用内存
- 首次运行需下载约 **13 GB** SDXL 模型（HuggingFace）；可选 ControlNet 再加约 5 GB

## 安装

```bash
cd /Users/mingyue/wwwpro/study/unwatermarkai
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**国内网络必须配置 HuggingFace 镜像**，否则模型下载会失败：

```bash
cp .env.example .env
# .env 中已默认设置：
#   HF_ENDPOINT=https://hf-mirror.com
#   HF_HUB_DISABLE_XET=1   # 镜像站必须禁用 XET，否则会 401
#   PIPELINE=sdxl          # 仅 SDXL（~13 GB）；改为 controlnet 可保留文字/人脸（~17 GB）
```

可选：设置 HuggingFace Token（提高下载限速）

```bash
# 在 .env 中添加
HF_TOKEN=hf_your_token_here
```

## 启动

```bash
source .venv/bin/activate
chmod +x scripts/start.sh
./scripts/start.sh
```

浏览器打开 http://127.0.0.1:8080

### 首次使用：预下载模型（推荐）

国内网络建议先执行（SDXL 约 13 GB，需较长时间）：

```bash
./scripts/download_models.sh
```

若图片含复杂文字/人脸、需更好保真，可在 `.env` 中设置 `PIPELINE=controlnet` 后重新下载（总量约 17 GB）。

## 使用流程

1. 上传 PNG / JPEG / WebP 图片（最大 20 MB）
2. 点击「去除 SynthID 水印」
3. 等待处理完成（首次会下载模型，可能需要数分钟）
4. 点击「下载新图片」

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 检查 GPU 依赖和设备 |
| POST | `/api/remove-synthid` | 上传图片，返回 `job_id` |
| GET | `/api/jobs/{job_id}` | 查询任务状态 |
| GET | `/api/jobs/{job_id}/download` | 下载处理结果 |

## 原理

SynthID 通过 SDXL img2img 扩散再生去除：将图片编码到 latent 空间，按厂商自适应 strength 加噪后去噪重建，破坏不可见水印模式。默认使用纯 SDXL pipeline（`PIPELINE=sdxl`）；可选 `PIPELINE=controlnet` 加载 Canny ControlNet 以更好保留文字和人脸结构。

## 注意事项

- 处理是**有损**的，会轻微柔化细节
- 纯 SDXL 模式对含文字/平面填色的图片，SynthID 可能去除不彻底；可改用 `PIPELINE=controlnet`
- 无法在本地验证 SynthID 是否完全去除，请用 Gemini App 的 "Verify with SynthID" 确认
- 大图（长边 > 1024px）自动启用分块处理以防 MPS 内存不足
- 服务为单任务队列，同时只处理一张图片
- **内存**：启动 Web 服务几乎不占模型内存；**首次处理图片**时才加载 SDXL（约 8–13 GB）。16 GB 内存 Mac 请保持 `.env` 中 `MAX_RESOLUTION=1536`，并关闭其他占内存应用
- 不要用 `RELOAD=1` 启动（热重载会多占一份进程内存）

## 常见问题

**启动后内存就被吃光**

原因：旧版本启动时会预加载整个 SDXL 模型（~13 GB），且 `--reload` 会多开一个进程。

已修复：现在改为**首次处理图片时才加载模型**，且默认关闭热重载。请重新启动：

```bash
PORT=8081 ./scripts/start.sh
```

若 16 GB 内存仍不够，在 `.env` 中设置 `MAX_RESOLUTION=1024`。

**`Can't load config for 'xinsir/controlnet-canny-sdxl-1.0'`**

原因是无法访问 HuggingFace。解决：

```bash
cp .env.example .env   # 确保有 HF_ENDPOINT=https://hf-mirror.com
./scripts/download_models.sh
./scripts/start.sh       # 重启服务
```

**下载时报 `401 Unauthorized` / `cas-server.xethub.hf.co`**

新版 `huggingface_hub` 默认走 XET 加速下载，但国内镜像不支持。确保 `.env` 中有：

```bash
HF_HUB_DISABLE_XET=1
```

然后重新运行 `./scripts/download_models.sh`。

## 许可

本项目封装层代码可自由使用。核心算法来自 [remove-ai-watermarks](https://github.com/wiltodelta/remove-ai-watermarks)（Apache-2.0）。
