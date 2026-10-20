"""Say one priced line on this computer. The voice module is not connected."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

from scale_host.fusion import Sale
from scale_host.recognized_sale import price_simulated_banana

_SPOKEN_NAMES = {"banana": "香蕉", "香蕉": "香蕉"}
_SPEAK = (
    "Add-Type -AssemblyName System.Speech; "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voice = $s.GetInstalledVoices() | "
    "Where-Object { $_.VoiceInfo.Culture.Name -like 'zh*' } | "
    "Select-Object -First 1; "
    "if ($null -ne $voice) { $s.SelectVoice($voice.VoiceInfo.Name) }; "
    "$s.Speak($env:SCALE_SPEAK_TEXT)"
)


class Speaker:
    def say(self, text: str) -> None:
        raise NotImplementedError


class RecordingSpeaker(Speaker):
    def __init__(self) -> None:
        self.lines: list[str] = []

    def say(self, text: str) -> None:
        self.lines.append(text)


class WindowsSpeaker(Speaker):
    """Built-in Windows speech. A failure must not change the sale."""

    def say(self, text: str) -> None:
        env = os.environ.copy()
        env["SCALE_SPEAK_TEXT"] = text
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", _SPEAK],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("computer speaker failed") from exc
        if completed.returncode != 0:
            raise RuntimeError("computer speaker failed")


def announcement(sale: Sale) -> str:
    name = _SPOKEN_NAMES.get(sale.label, sale.label)
    return f"{name}，{sale.weight_g:g}克，{sale.amount_yuan:.2f}元"


def deliver(sale: Sale | None, speaker: Speaker) -> tuple[str, bool] | None:
    if sale is None:
        return None
    text = announcement(sale)
    try:
        speaker.say(text)
    except Exception:
        return text, False
    return text, True


def main() -> None:
    try:
        sale = asyncio.run(price_simulated_banana())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    spoken = deliver(sale, WindowsSpeaker())
    if spoken is None:
        raise SystemExit(2)
    text, heard = spoken
    print(f"product: {sale.label}")
    print(f"weight_g: {sale.weight_g}")
    print(f"price: {sale.amount_yuan:.2f}")
    print(f"spoken_line: {text}")
    print(f"spoken: {'yes' if heard else 'no'}")
    print("nutrition_spoken: no")
    print("sent_to_internet: no")
    print("com_open: no")
    if sale.amount_yuan != 3.92 or sale.weight_g != 326.4:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
