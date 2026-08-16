#!/usr/bin/env python3
"""Visual ear — spectrogram images for a reader who can see but not hear.

Three views, tuned for legibility to a vision model rather than prettiness:

  overview.png   Full-track mel spectrogram with bar-number gridlines, RMS
                 energy lane, and section boundaries. One glance answers: does
                 the arrangement move, where is the energy, is there top end.
  stems.png      Per-stem mel spectrograms stacked (drums / bass / other /
                 full). Shows masking, mud, and which stem owns which band.
  loop.png       4-bar zoom at high time resolution with 16th-note gridlines:
                 transient sharpness, kick decay length, hat placement — the
                 things that live between the beats.

High-contrast magma on near-black, generous font sizes, frequency axis in
kHz with log spacing. Every x-axis is labeled in BARS (musical time).
"""
import numpy as np
import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STYLE = {"facecolor": "#0d0d12", "text": "#e8e8f0", "grid": "#ffffff",
         "accent": "#5ac8fa"}


def _mel(y, sr, n_mels=160, fmax=16000, hop=512):
    M = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mels, fmax=fmax,
                                       hop_length=hop, power=2.0)
    return librosa.power_to_db(M, ref=np.max)


def _style_ax(ax):
    ax.set_facecolor(STYLE["facecolor"])
    ax.tick_params(colors=STYLE["text"], labelsize=11)
    for s in ax.spines.values():
        s.set_color("#333")


def _bar_axis(ax, dur, tempo, downbeat=0.0, every=4):
    bar_s = 60.0 / tempo * 4
    n_bars = int((dur - downbeat) / bar_s) + 1
    ticks, labels = [], []
    for b in range(0, n_bars, every):
        t = downbeat + b * bar_s
        if t > dur:
            break
        ticks.append(t)
        labels.append(str(b + 1))
        ax.axvline(t, color=STYLE["grid"], alpha=0.18, lw=0.7, zorder=3)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_xlabel("bar", color=STYLE["text"], fontsize=11)


def _draw_mel(ax, M, sr, dur, fmax=16000, hop=512):
    ax.imshow(M, aspect="auto", origin="lower", cmap="magma",
              extent=[0, dur, 0, M.shape[0]], vmin=-70, vmax=0)
    mel_f = librosa.mel_frequencies(n_mels=M.shape[0], fmax=fmax)
    marks = [50, 100, 250, 500, 1000, 2000, 4000, 8000, 14000]
    ticks = [np.argmin(np.abs(mel_f - m)) for m in marks]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{m/1000:g}k" if m >= 1000 else str(m) for m in marks])
    _style_ax(ax)


def overview(y, sr, tempo, downbeat, sections, out_path, title=""):
    dur = len(y) / sr
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(16, 7.5), height_ratios=[4, 1], sharex=True,
        facecolor=STYLE["facecolor"], constrained_layout=True)
    M = _mel(y, sr)
    _draw_mel(ax1, M, sr, dur)
    ax1.set_ylabel("Hz", color=STYLE["text"], fontsize=11)
    ax1.set_title(title or "overview", color=STYLE["text"], fontsize=13)

    hop = 1024
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    ax2.fill_between(t, 20 * np.log10(rms + 1e-9), -60,
                     color=STYLE["accent"], alpha=0.7)
    ax2.set_ylim(-45, 0)
    ax2.set_ylabel("RMS dB", color=STYLE["text"], fontsize=10)
    _style_ax(ax2)
    for s in sections or []:
        for ax in (ax1, ax2):
            ax.axvline(s["start_s"], color=STYLE["accent"], alpha=0.9, lw=1.4,
                       ls="--", zorder=4)
    _bar_axis(ax2, dur, tempo, downbeat, every=4)
    fig.savefig(out_path, dpi=110, facecolor=STYLE["facecolor"])
    plt.close(fig)


def stems_figure(stems, sr, tempo, downbeat, out_path):
    """stems: ordered {name: mono array}. Full mix last is conventional."""
    n = len(stems)
    fig, axes = plt.subplots(n, 1, figsize=(16, 2.6 * n), sharex=True,
                             facecolor=STYLE["facecolor"], constrained_layout=True)
    axes = np.atleast_1d(axes)
    dur = max(len(s) for s in stems.values()) / sr
    for ax, (name, s) in zip(axes, stems.items()):
        _draw_mel(ax, _mel(s, sr, n_mels=112), sr, len(s) / sr)
        ax.set_ylabel(name, color=STYLE["text"], fontsize=12)
    _bar_axis(axes[-1], dur, tempo, downbeat, every=8)
    fig.savefig(out_path, dpi=100, facecolor=STYLE["facecolor"])
    plt.close(fig)


def loop_zoom(y, sr, tempo, downbeat, out_path, bars=4, start_bar=None):
    """High-res zoom. start_bar defaults to the loudest 4-bar window."""
    bar_s = 60.0 / tempo * 4
    n_bars = int((len(y) / sr - downbeat) / bar_s)
    if n_bars < 1:
        return
    bars = min(bars, n_bars)
    if start_bar is None:
        rms = [np.sqrt(np.mean(y[int((downbeat + b * bar_s) * sr):
                                 int((downbeat + (b + bars) * bar_s) * sr)] ** 2))
               for b in range(0, max(1, n_bars - bars + 1))]
        start_bar = int(np.argmax(rms))
    a = downbeat + start_bar * bar_s
    seg = y[int(a * sr):int((a + bars * bar_s) * sr)]
    dur = len(seg) / sr

    fig, ax = plt.subplots(figsize=(16, 6), facecolor=STYLE["facecolor"],
                           constrained_layout=True)
    _draw_mel(ax, _mel(seg, sr, n_mels=200, hop=128), sr, dur, hop=128)
    step = bar_s / 16
    for i in range(bars * 16 + 1):
        t = i * step
        if t > dur:
            break
        strong = i % 16 == 0
        beat = i % 4 == 0
        ax.axvline(t, color=STYLE["grid"],
                   alpha=0.5 if strong else (0.25 if beat else 0.08),
                   lw=1.3 if strong else 0.6, zorder=3)
    ax.set_xticks([i * bar_s for i in range(bars + 1)])
    ax.set_xticklabels([str(start_bar + 1 + i) for i in range(bars + 1)])
    ax.set_xlabel("bar (gridlines = 16ths)", color=STYLE["text"], fontsize=11)
    ax.set_title(f"loop zoom — bars {start_bar + 1}-{start_bar + bars}",
                 color=STYLE["text"], fontsize=13)
    fig.savefig(out_path, dpi=110, facecolor=STYLE["facecolor"])
    plt.close(fig)
