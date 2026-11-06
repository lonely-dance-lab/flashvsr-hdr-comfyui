# ComfyUI-HLG-HDR-Save

把 IMAGE 帧序列保存为 **HLG HDR** 视频：提亮曲线 → BT.2020 10-bit YUV → HEVC（libx265）→ HLG / BT.2020 标记，`hvc1` 标签。

## 安装

```bash
cp -r ComfyUI-HLG-HDR-Save ComfyUI/custom_nodes/
```

依赖 ComfyUI 自带的 PyAV（需包含 `libx265` 编码器），无需额外安装。

## 节点

**保存 HDR 视频 (HLG · HEVC 10-bit)** · 分类 `FlashVSR` · 类名 `HLGHDRSaveVideo`

| 输入 | 类型 | 说明 |
| --- | --- | --- |
| images | IMAGE | 视频帧 |
| fps | FLOAT | 帧率，自动吸附 24 / 25 / 30 / 60 / 23.976 等标准值 |
| brightness | 选项 | `特别亮` / `标准亮` / `不提亮` |
| crf | INT | 默认 16 |
| preset | 选项 | `fast` / `medium` / `slow` |
| filename_prefix | STRING | 默认 `video/flashvsr_hdr` |
| audio | AUDIO（可选） | 原声，AAC 编码 |

输出到 `ComfyUI/output/`，在节点上可预览。
