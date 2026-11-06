"""HLG HDR 视频保存：提亮曲线 + 10-bit HEVC (libx265) + HLG/BT.2020 标记。

做法和 FFmpeg 版一致：
  curves 提亮 -> RGB 转 BT.2020 矩阵的 10-bit YUV（limited range）-> 标记 HLG / BT.2020 -> x265 编码，hvc1 标签。
"""
import math
import os
from fractions import Fraction

import av
import numpy as np
import torch
from av.video.reformatter import ColorPrimaries, ColorRange, ColorTrc

import folder_paths

BT2020_NCL = 9

# 与桌面上 HDR / HDR_extra 版本相同的曲线控制点
PRESETS = {
    "特别亮": [(0, 0), (0.1, 0.13), (0.25, 0.36), (0.5, 0.7), (0.75, 0.92), (0.9, 0.99), (1, 1)],
    "标准亮": [(0, 0), (0.25, 0.25), (0.5, 0.6), (0.75, 0.88), (0.9, 0.98), (1, 1)],
    "不提亮": [(0, 0), (1, 1)],
}


def _monotone_lut(points, size=65536):
    """Fritsch–Carlson 单调三次插值，生成 0..1 的查找表。"""
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    n = len(xs)
    x = np.linspace(0.0, 1.0, size)
    if n == 2:
        return np.interp(x, xs, ys).astype(np.float32)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros(n)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    idx = np.clip(np.searchsorted(xs, x, side="right") - 1, 0, n - 2)
    t = (x - xs[idx]) / h[idx]
    t2, t3 = t * t, t * t * t
    y = ((2 * t3 - 3 * t2 + 1) * ys[idx] + (t3 - 2 * t2 + t) * h[idx] * m[idx]
         + (-2 * t3 + 3 * t2) * ys[idx + 1] + (t3 - t2) * h[idx] * m[idx + 1])
    return np.clip(y, 0.0, 1.0).astype(np.float32)


def _snap_rate(fps):
    """把 24.0047 这类带误差的帧率吸附到标准帧率。"""
    for r in (Fraction(24000, 1001), Fraction(30000, 1001), Fraction(60000, 1001)):
        if abs(fps - float(r)) < 0.003:
            return r
    if abs(fps - round(fps)) < 0.02:
        return Fraction(int(round(fps)), 1)
    return Fraction(round(fps * 1000), 1000)


class HLGHDRSaveVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "视频帧，比如 FlashVSR 的输出"}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.001}),
                "brightness": (list(PRESETS.keys()), {"default": "特别亮", "tooltip": "提亮曲线。特别亮 = 桌面 3.mp4 的效果"}),
                "crf": ("INT", {"default": 16, "min": 0, "max": 51, "tooltip": "越小画质越好、文件越大"}),
                "preset": (["fast", "medium", "slow"], {"default": "fast"}),
                "filename_prefix": ("STRING", {"default": "video/flashvsr_hdr"}),
            },
            "optional": {
                "audio": ("AUDIO",),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "FlashVSR"
    DESCRIPTION = "提亮后保存为 10-bit HEVC + HLG HDR 的 MP4，苹果设备 / Safari / Chrome 可直接播放。需要 HDR 屏幕才能看到变亮。"

    def save(self, images, fps, brightness, crf, preset, filename_prefix, audio=None):
        frames, H, W, _ = images.shape
        H2, W2 = H - H % 2, W - W % 2
        out_dir, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory(), W2, H2)
        file = f"{filename}_{counter:05}_.mp4"
        path = os.path.join(out_dir, file)

        lut = torch.from_numpy(_monotone_lut(PRESETS[brightness]))
        rate = _snap_rate(fps)
        tb = Fraction(rate.denominator, rate.numerator)

        with av.open(path, mode="w", format="mp4", options={"movflags": "faststart"}) as out:
            vs = out.add_stream("libx265", rate=rate)
            vs.width, vs.height = W2, H2
            vs.time_base = tb
            vs.codec_context.time_base = tb
            vs.pix_fmt = "yuv420p10le"
            vs.codec_context.codec_tag = "hvc1"
            vs.codec_context.color_primaries = ColorPrimaries.BT2020
            vs.codec_context.color_trc = ColorTrc.ARIB_STD_B67
            vs.codec_context.colorspace = BT2020_NCL
            vs.codec_context.color_range = ColorRange.MPEG
            vs.options = {
                "crf": str(crf),
                "preset": preset,
                "x265-params": "log-level=error:colorprim=bt2020:transfer=arib-std-b67:"
                               "colormatrix=bt2020nc:range=limited:atc-sei=18",
            }

            a_stream = None
            if audio is not None:
                sr = int(audio["sample_rate"])
                wf = audio["waveform"][0, :, :math.ceil(sr / float(fps) * frames)]
                layout = {1: "mono", 2: "stereo", 6: "5.1"}.get(wf.shape[0], "stereo")
                a_stream = out.add_stream("aac", rate=sr, layout=layout)

            for i in range(frames):
                img = images[i, :H2, :W2, :].float().clamp(0, 1).cpu()
                img = lut[(img * 65535).round().long()]
                arr = (img * 65535).round().clamp(0, 65535).numpy().astype(np.uint16)
                vf = av.VideoFrame.from_ndarray(arr, format="rgb48le")
                vf = vf.reformat(format="yuv420p10le", dst_colorspace=BT2020_NCL, dst_color_range=ColorRange.MPEG)
                vf.color_primaries = ColorPrimaries.BT2020
                vf.color_trc = ColorTrc.ARIB_STD_B67
                vf.colorspace = BT2020_NCL
                vf.color_range = ColorRange.MPEG
                vf.pts = i
                vf.time_base = tb
                for p in vs.encode(vf):
                    out.mux(p)
            for p in vs.encode(None):
                out.mux(p)

            if a_stream is not None:
                af = av.AudioFrame.from_ndarray(wf.float().cpu().contiguous().numpy(), format="fltp", layout=layout)
                af.sample_rate = sr
                af.pts = 0
                for p in a_stream.encode(af):
                    out.mux(p)
                for p in a_stream.encode(None):
                    out.mux(p)

        return {"ui": {"images": [{"filename": file, "subfolder": subfolder, "type": "output"}], "animated": [True]}}


NODE_CLASS_MAPPINGS = {"HLGHDRSaveVideo": HLGHDRSaveVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"HLGHDRSaveVideo": "保存 HDR 视频 (HLG · HEVC 10-bit)"}
