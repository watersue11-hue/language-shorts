from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from moviepy import (
        AudioClip,
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )
except ImportError:
    from moviepy.editor import (
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )
    from moviepy.audio.AudioClip import AudioClip


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("free_language_shorts")

AUDIO_CACHE_DIR = Path(".audio_cache_free")


LANG_OPTIONS = {
    "스페인어": "es",
    "영어": "en",
    "일본어": "ja",
    "중국어": "zh",
    "프랑스어": "fr",
    "독일어": "de",
    "이탈리아어": "it",
}

LANG_DISPLAY_NAMES: Dict[str, str] = {
    "ko": "한국어",
    "es": "스페인어",
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "fr": "프랑스어",
    "de": "독일어",
    "it": "이탈리아어",
}

GTTS_LANG: Dict[str, str] = {
    "ko": "ko",
    "es": "es",
    "en": "en",
    "ja": "ja",
    "zh": "zh-CN",
    "fr": "fr",
    "de": "de",
    "it": "it",
}


LANG_FONT_CANDIDATES: Dict[str, List[str]] = {
    "ko": [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgunbd.ttf",
        "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",
    ],
    "ja": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    ],
    "zh": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
    "en": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
}
for _latin_lang in ["es", "fr", "de", "it"]:
    LANG_FONT_CANDIDATES[_latin_lang] = LANG_FONT_CANDIDATES["en"]


FREE_PHRASES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "es": {
        "기본": [
            {"kr": "안녕하세요", "target": "Hola", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "Gracias", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "De nada", "tip": "대답으로 자연스러움"},
            {"kr": "실례합니다", "target": "Disculpe", "tip": "말을 걸 때 사용"},
            {"kr": "다시 말해 주세요", "target": "Repítalo, por favor", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "Está bien", "tip": "문제없다는 느낌"},
            {"kr": "좋아요", "target": "Me gusta", "tip": "마음에 들 때"},
            {"kr": "잘 모르겠어요", "target": "No lo sé", "tip": "모를 때 사용"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "Aquí tiene mi pasaporte", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "Vengo de turismo", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "¿Cuántos días se queda?", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "Me quedo una semana", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "¿Dónde recojo mi equipaje?", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "Un café, por favor", "tip": "가장 간단한 주문"},
            {"kr": "아이스로 주세요", "target": "Con hielo, por favor", "tip": "얼음 요청"},
            {"kr": "포장해 주세요", "target": "Para llevar, por favor", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "¿Cuánto cuesta?", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "¿Aceptan tarjeta?", "tip": "카드 결제 확인"},
        ],
        "여행": [
            {"kr": "여기 어떻게 가요?", "target": "¿Cómo llego aquí?", "tip": "길 물을 때"},
            {"kr": "역이 어디예요?", "target": "¿Dónde está la estación?", "tip": "장소 찾기"},
            {"kr": "사진 찍어 주세요", "target": "¿Puede tomarme una foto?", "tip": "여행 필수 표현"},
            {"kr": "추천해 주세요", "target": "¿Qué me recomienda?", "tip": "추천 요청"},
            {"kr": "화장실 어디예요?", "target": "¿Dónde está el baño?", "tip": "급할 때 필수"},
        ],
    },
    "en": {
        "기본": [
            {"kr": "안녕하세요", "target": "Hello", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "Thank you", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "You're welcome", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "Excuse me", "tip": "말 걸 때 사용"},
            {"kr": "다시 말해 주세요", "target": "Could you say that again?", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "It's okay", "tip": "문제없다는 느낌"},
            {"kr": "좋아요", "target": "I like it", "tip": "마음에 들 때"},
            {"kr": "잘 모르겠어요", "target": "I'm not sure", "tip": "모를 때 부드럽게"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "Here is my passport", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "I'm here for tourism", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "How long will you stay?", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "I'll stay for a week", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "Where can I get my luggage?", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "Can I get a coffee?", "tip": "자연스러운 주문"},
            {"kr": "아이스로 주세요", "target": "Can I get it iced?", "tip": "아이스 요청"},
            {"kr": "포장해 주세요", "target": "To go, please", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "How much is it?", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "Do you take cards?", "tip": "카드 결제 확인"},
        ],
        "DM": [
            {"kr": "답장 늦어서 미안", "target": "Sorry for the late reply", "tip": "DM 답장 시작"},
            {"kr": "진짜 웃기다", "target": "That's so funny", "tip": "리액션 표현"},
            {"kr": "나도 그렇게 생각해", "target": "I feel the same way", "tip": "공감할 때"},
            {"kr": "오늘 어땠어?", "target": "How was your day?", "tip": "가볍게 묻기"},
            {"kr": "완전 좋아", "target": "I love it", "tip": "강한 긍정"},
        ],
    },
    "ja": {
        "기본": [
            {"kr": "안녕하세요", "target": "こんにちは", "tip": "낮 시간 기본 인사"},
            {"kr": "감사합니다", "target": "ありがとうございます", "tip": "정중한 감사 표현"},
            {"kr": "천만에요", "target": "どういたしまして", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "すみません", "tip": "말 걸거나 사과할 때"},
            {"kr": "다시 말해 주세요", "target": "もう一度言ってください", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "大丈夫です", "tip": "괜찮다는 표현"},
            {"kr": "좋아요", "target": "いいですね", "tip": "긍정 리액션"},
            {"kr": "잘 모르겠어요", "target": "よくわかりません", "tip": "모를 때 사용"},
        ],
        "공항": [
            {"kr": "여권 여기 있습니다", "target": "パスポートはこちらです", "tip": "입국 심사에서"},
            {"kr": "관광하러 왔어요", "target": "観光で来ました", "tip": "방문 목적 설명"},
            {"kr": "며칠 머무르세요?", "target": "何日滞在しますか？", "tip": "체류 기간 질문"},
            {"kr": "일주일 머물 거예요", "target": "一週間滞在します", "tip": "체류 기간 대답"},
            {"kr": "짐은 어디서 찾나요?", "target": "荷物はどこで受け取れますか？", "tip": "수하물 찾을 때"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "コーヒーを一つください", "tip": "기본 주문"},
            {"kr": "아이스로 주세요", "target": "アイスでお願いします", "tip": "아이스 요청"},
            {"kr": "포장해 주세요", "target": "持ち帰りでお願いします", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "いくらですか？", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "カードは使えますか？", "tip": "카드 결제 확인"},
        ],
    },
    "zh": {
        "기본": [
            {"kr": "안녕하세요", "target": "你好", "tip": "가장 기본적인 인사"},
            {"kr": "감사합니다", "target": "谢谢", "tip": "고마울 때 사용"},
            {"kr": "천만에요", "target": "不客气", "tip": "감사 인사 대답"},
            {"kr": "실례합니다", "target": "打扰一下", "tip": "말 걸 때 자연스러움"},
            {"kr": "다시 말해 주세요", "target": "请再说一遍", "tip": "못 들었을 때"},
            {"kr": "괜찮아요", "target": "没关系", "tip": "문제없다는 표현"},
            {"kr": "좋아요", "target": "很好", "tip": "긍정 리액션"},
            {"kr": "잘 모르겠어요", "target": "我不太清楚", "tip": "모를 때 부드럽게"},
        ],
        "카페": [
            {"kr": "커피 한 잔 주세요", "target": "请给我一杯咖啡", "tip": "기본 주문"},
            {"kr": "아이스로 주세요", "target": "请加冰", "tip": "얼음 요청"},
            {"kr": "포장해 주세요", "target": "请打包", "tip": "테이크아웃"},
            {"kr": "얼마예요?", "target": "多少钱？", "tip": "가격 질문"},
            {"kr": "카드 돼요?", "target": "可以刷卡吗？", "tip": "카드 결제 확인"},
        ],
        "여행": [
            {"kr": "여기 어떻게 가요?", "target": "这里怎么走？", "tip": "길 물을 때"},
            {"kr": "역이 어디예요?", "target": "车站在哪里？", "tip": "장소 찾기"},
            {"kr": "사진 찍어 주세요", "target": "可以帮我拍照吗？", "tip": "여행 필수 표현"},
            {"kr": "추천해 주세요", "target": "你有什么推荐？", "tip": "추천 요청"},
            {"kr": "화장실 어디예요?", "target": "洗手间在哪里？", "tip": "급할 때 필수"},
        ],
    },
}

FREE_PHRASES["fr"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Bonjour", "tip": "기본 인사"},
        {"kr": "감사합니다", "target": "Merci", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Excusez-moi", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "C'est combien ?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Répétez, s'il vous plaît", "tip": "못 들었을 때"},
    ]
}
FREE_PHRASES["de"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Hallo", "tip": "기본 인사"},
        {"kr": "감사합니다", "target": "Danke", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Entschuldigung", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "Wie viel kostet das?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Bitte sagen Sie das noch einmal", "tip": "못 들었을 때"},
    ]
}
FREE_PHRASES["it"] = {
    "기본": [
        {"kr": "안녕하세요", "target": "Ciao", "tip": "가벼운 인사"},
        {"kr": "감사합니다", "target": "Grazie", "tip": "고마울 때 사용"},
        {"kr": "실례합니다", "target": "Mi scusi", "tip": "말 걸 때 사용"},
        {"kr": "얼마예요?", "target": "Quanto costa?", "tip": "가격 질문"},
        {"kr": "다시 말해 주세요", "target": "Può ripetere?", "tip": "못 들었을 때"},
    ]
}


@dataclass
class VideoConfig:
    is_shorts: bool = True
    shadowing_pause: float = 2.2
    gap_after_kr: float = 0.8
    tail_padding: float = 1.0
    output_dir: Path = Path("outputs")
    words_per_topic: int = 5

    source_lang: str = "ko"
    target_lang: str = "es"

    use_tts: bool = True
    slow_tts: bool = False

    use_illustration_bg: bool = True
    illustration_style: str = "clean"

    bgm_path: Optional[str] = "assets/bgm.mp3"
    bgm_volume: float = 0.07
    bg_video_path: Optional[str] = "assets/bg_loop.mp4"

    brand_name: str = ""
    logo_text: str = ""
    intro_duration: float = 1.0
    title_label: str = "오늘의 표현"

    @property
    def size(self) -> Tuple[int, int]:
        return (720, 1280) if self.is_shorts else (1280, 720)

    @property
    def kr_font_size(self) -> int:
        return 54 if self.is_shorts else 60

    @property
    def target_font_size(self) -> int:
        return 78 if self.is_shorts else 82

    @property
    def tip_font_size(self) -> int:
        return 32 if self.is_shorts else 36


def safe_filename(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:80] or "video"


def get_free_script(topic: str, target_lang: str, n: int) -> List[Dict[str, str]]:
    bank = FREE_PHRASES.get(target_lang, FREE_PHRASES["en"])
    topic_lower = topic.lower()

    selected_key = "기본"
    keyword_map = {
        "공항": ["공항", "입국", "여권", "airport"],
        "카페": ["카페", "커피", "주문", "cafe", "coffee"],
        "여행": ["여행", "길", "역", "사진", "travel"],
        "DM": ["dm", "디엠", "답장", "댓글", "인스타"],
    }

    for key, keywords in keyword_map.items():
        if key in bank and any(k in topic_lower for k in keywords):
            selected_key = key
            break

    items = bank.get(selected_key, bank.get("기본", []))
    if len(items) < n:
        base_items = bank.get("기본", [])
        merged = items + [x for x in base_items if x not in items]
        items = merged

    if not items:
        return []

    if len(items) >= n:
        return items[:n]

    out = []
    for i in range(n):
        out.append(dict(items[i % len(items)]))
    return out


def parse_manual_items(text: str, target_lang: str) -> List[Dict[str, str]]:
    items = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            items.append(
                {
                    "kr": parts[0],
                    "target": parts[1],
                    "tip": parts[2] if len(parts) >= 3 and parts[2] else "소리 내서 따라 해보세요",
                }
            )
    return items


# --------------------------------------------------------------------------- #
# moviepy 호환
# --------------------------------------------------------------------------- #
def _with_start(clip, t: float):
    return clip.with_start(t) if hasattr(clip, "with_start") else clip.set_start(t)


def _with_duration(clip, d: float):
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)


def _with_position(clip, pos):
    return clip.with_position(pos) if hasattr(clip, "with_position") else clip.set_position(pos)


def _with_audio(clip, audio):
    return clip.with_audio(audio) if hasattr(clip, "with_audio") else clip.set_audio(audio)


def _without_audio(clip):
    if hasattr(clip, "without_audio"):
        return clip.without_audio()
    return _with_audio(clip, None)


def _subclip(clip, start: float, end: float):
    return clip.subclipped(start, end) if hasattr(clip, "subclipped") else clip.subclip(start, end)


def _resize(clip, new_size: Tuple[int, int]):
    return clip.resized(new_size) if hasattr(clip, "resized") else clip.resize(newsize=new_size)


def _scale_volume(clip, factor: float):
    if hasattr(clip, "volumex"):
        return clip.volumex(factor)
    try:
        from moviepy.audio.fx import MultiplyVolume
        return clip.with_effects([MultiplyVolume(factor)])
    except Exception:
        try:
            from moviepy.audio.fx.all import volumex
            return volumex(clip, factor)
        except Exception:
            return clip


def _crop(clip, x_center: float, y_center: float, width: int, height: int):
    try:
        from moviepy.video.fx import Crop
        return clip.with_effects([Crop(x_center=x_center, y_center=y_center, width=width, height=height)])
    except Exception:
        try:
            from moviepy.video.fx.all import crop
            return crop(clip, x_center=x_center, y_center=y_center, width=width, height=height)
        except Exception:
            return clip


def _loop_to_duration(clip, duration: float):
    try:
        from moviepy.video.fx import Loop
        return clip.with_effects([Loop(duration=duration)])
    except Exception:
        try:
            from moviepy.video.fx.all import loop
            return loop(clip, duration=duration)
        except Exception:
            reps = max(1, math.ceil(duration / max(clip.duration, 0.1)))
            looped = concatenate_videoclips([clip] * reps)
            return _subclip(looped, 0, duration)


# --------------------------------------------------------------------------- #
# 오디오
# --------------------------------------------------------------------------- #
def _audio_cache_path(text: str, lang: str, slow: bool) -> Path:
    key = hashlib.sha256(f"{text}|{lang}|{slow}".encode("utf-8")).hexdigest()[:20]
    return AUDIO_CACHE_DIR / f"{key}.mp3"


def _write_silence(path: Path, duration: float = 0.9, fps: int = 44100) -> None:
    def frame(t):
        if isinstance(t, np.ndarray):
            return np.zeros_like(t)
        return 0.0

    silent = AudioClip(frame, duration=duration, fps=fps)
    silent.write_audiofile(str(path), fps=fps, logger=None)
    silent.close()


def free_tts_to_file(text: str, lang: str, path: Path, slow: bool, use_tts: bool) -> None:
    if not use_tts:
        _write_silence(path)
        return

    AUDIO_CACHE_DIR.mkdir(exist_ok=True)
    gtts_lang = GTTS_LANG.get(lang, "en")
    cache = _audio_cache_path(text, gtts_lang, slow)

    if cache.exists():
        shutil.copy(cache, path)
        return

    try:
        tts = gTTS(text=text, lang=gtts_lang, slow=slow)
        tts.save(str(path))
        shutil.copy(path, cache)
    except Exception as e:
        log.warning("gTTS 실패, 무음으로 대체합니다: %s", e)
        _write_silence(path)


# --------------------------------------------------------------------------- #
# 폰트/텍스트 이미지
# --------------------------------------------------------------------------- #
def get_safe_font(lang: str, font_size: int):
    candidates = LANG_FONT_CANDIDATES.get(lang, LANG_FONT_CANDIDATES["en"])
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, font_size)
    return ImageFont.load_default(size=font_size)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_to_width(text: str, font, max_width: int) -> List[str]:
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    if " " in text:
        tokens = text.split(" ")
        joiner = " "
    else:
        tokens = list(text)
        joiner = ""

    lines = []
    current = ""

    for token in tokens:
        candidate = (current + joiner + token).strip() if current else token
        width, _ = _text_size(draw, candidate, font)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = token

    if current:
        lines.append(current)

    return lines[:4]


def make_text_image_clip(
    text: str,
    lang: str,
    font_size: int,
    color: Tuple[int, int, int, int],
    video_size: Tuple[int, int],
    max_width_ratio: float,
    duration: float,
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 230),
    stroke_width: int = 4,
):
    font = get_safe_font(lang, font_size)
    max_width = int(video_size[0] * max_width_ratio)
    lines = wrap_text_to_width(text, font, max_width)

    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    sizes = [_text_size(draw, line, font) for line in lines]
    line_gap = int(font_size * 0.25)
    padding_x = 48
    padding_y = 24
    img_w = max([w for w, _ in sizes] + [1]) + padding_x * 2
    img_h = sum(h for _, h in sizes) + line_gap * (len(lines) - 1) + padding_y * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = padding_y
    for line, (w, h) in zip(lines, sizes):
        x = (img_w - w) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        y += h + line_gap

    return _with_duration(ImageClip(np.array(img)), duration)


def layout_text_block(kr_clip, target_clip, tip_clip, video_size: Tuple[int, int]):
    w, h = video_size
    kr_y = int(h * 0.245)
    target_y = int(h * 0.430)
    tip_y = int(h * 0.690)
    return (
        ("center", kr_y),
        ("center", target_y),
        ("center", tip_y),
    )


def make_progress_clip(idx: int, total: int, cfg: VideoConfig, duration: float):
    clip = make_text_image_clip(
        text=f"{idx + 1} / {total}",
        lang="en",
        font_size=28 if cfg.is_shorts else 34,
        color=(32, 36, 44, 255),
        video_size=cfg.size,
        max_width_ratio=0.30,
        duration=duration,
        stroke_width=0,
    )
    x = cfg.size[0] - clip.w - int(cfg.size[0] * 0.13)
    y = int(cfg.size[1] * 0.083)
    return _with_position(clip, (x, y))


# --------------------------------------------------------------------------- #
# 무료 벡터 일러스트 배경
# --------------------------------------------------------------------------- #
PALETTES = {
    "clean": {
        "top": (248, 251, 255),
        "bottom": (238, 244, 255),
        "accent": (35, 84, 190),
        "accent2": (35, 84, 190),
        "dark": (32, 36, 44),
        "paper": (255, 255, 255),
        "glass": (255, 255, 255, 230),
        "line": (220, 228, 242),
        "soft_blue": (233, 240, 255),
    },
}
PALETTES["warm"] = PALETTES["clean"]
PALETTES["pastel"] = PALETTES["clean"]
PALETTES["night"] = PALETTES["clean"]

def _gradient(size: Tuple[int, int], top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        col = [int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)]
        arr[y, :, :] = col
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _draw_soft_blob(img: Image.Image, xy, color, blur=38):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(xy, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def _rounded(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _scene_kind(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ["공항", "입국", "여권", "airport", "비행"]):
        return "airport"
    if any(k in t for k in ["카페", "커피", "cafe", "coffee"]):
        return "cafe"
    if any(k in t for k in ["여행", "길", "역", "사진", "travel"]):
        return "travel"
    if any(k in t for k in ["dm", "디엠", "댓글", "답장", "인스타", "메시지"]):
        return "dm"
    if any(k in t for k in ["학교", "대학", "수업", "시험", "공부", "school"]):
        return "school"
    if any(k in t for k in ["음식", "식당", "주문", "레스토랑", "restaurant"]):
        return "food"
    return "language"


def _draw_airport(draw, w, h, p):
    # window
    _rounded(draw, (int(w*0.11), int(h*0.13), int(w*0.89), int(h*0.42)), 52, (255,255,255,80), (255,255,255,120), 3)
    draw.rectangle((int(w*0.14), int(h*0.34), int(w*0.86), int(h*0.365)), fill=(255,255,255,60))
    # plane silhouette
    cx, cy = int(w*0.58), int(h*0.235)
    draw.polygon([(cx-190, cy+18), (cx+160, cy-22), (cx+210, cy), (cx+160, cy+22)], fill=(255,255,255,210))
    draw.polygon([(cx-20, cy-5), (cx+45, cy-105), (cx+85, cy-102), (cx+45, cy+8)], fill=(255,255,255,205))
    draw.polygon([(cx-70, cy+10), (cx-10, cy+90), (cx+30, cy+86), (cx+5, cy+2)], fill=(255,255,255,190))
    # passport
    _rounded(draw, (int(w*0.12), int(h*0.66), int(w*0.35), int(h*0.84)), 28, p["dark"]+(235,), None)
    draw.ellipse((int(w*0.19), int(h*0.71), int(w*0.28), int(h*0.76)), outline=p["accent"]+(255,), width=4)
    draw.line((int(w*0.18), int(h*0.79), int(w*0.30), int(h*0.79)), fill=p["accent"]+(255,), width=5)
    # suitcase
    _rounded(draw, (int(w*0.67), int(h*0.66), int(w*0.88), int(h*0.84)), 24, p["accent2"]+(235,), None)
    draw.arc((int(w*0.72), int(h*0.61), int(w*0.83), int(h*0.70)), 180, 360, fill=p["dark"]+(230,), width=8)
    draw.line((int(w*0.72), int(h*0.70), int(w*0.83), int(h*0.70)), fill=p["dark"]+(150,), width=5)


def _draw_cafe(draw, w, h, p):
    # table
    draw.ellipse((int(w*0.08), int(h*0.73), int(w*0.92), int(h*0.92)), fill=(70, 45, 58, 110))
    # cup
    _rounded(draw, (int(w*0.32), int(h*0.57), int(w*0.64), int(h*0.77)), 44, p["paper"]+(245,), (255,255,255,190), 3)
    draw.arc((int(w*0.58), int(h*0.61), int(w*0.75), int(h*0.73)), -80, 92, fill=p["paper"]+(240,), width=16)
    draw.rectangle((int(w*0.28), int(h*0.55), int(w*0.68), int(h*0.60)), fill=p["accent"]+(245,))
    # steam
    for xoff in [-70, 0, 70]:
        x = int(w*0.48) + xoff
        draw.arc((x-26, int(h*0.45), x+45, int(h*0.56)), 90, 270, fill=(255,255,255,150), width=6)
    # pastry/card
    draw.ellipse((int(w*0.12), int(h*0.69), int(w*0.33), int(h*0.80)), fill=p["accent"]+(230,))
    _rounded(draw, (int(w*0.68), int(h*0.54), int(w*0.88), int(h*0.68)), 22, (255,255,255,105), None)
    draw.line((int(w*0.71), int(h*0.59), int(w*0.84), int(h*0.59)), fill=p["dark"]+(120,), width=5)
    draw.line((int(w*0.71), int(h*0.63), int(w*0.80), int(h*0.63)), fill=p["dark"]+(90,), width=5)


def _draw_travel(draw, w, h, p):
    # map card
    _rounded(draw, (int(w*0.10), int(h*0.18), int(w*0.90), int(h*0.52)), 42, p["paper"]+(215,), (255,255,255,180), 3)
    # route
    pts = [(int(w*0.20), int(h*0.44)), (int(w*0.35), int(h*0.29)), (int(w*0.55), int(h*0.41)), (int(w*0.77), int(h*0.26))]
    for a, b in zip(pts, pts[1:]):
        draw.line((a, b), fill=p["accent2"]+(230,), width=9)
    for x,y in pts:
        draw.ellipse((x-16,y-16,x+16,y+16), fill=p["accent"]+(255,))
    # pin
    px, py = int(w*0.77), int(h*0.26)
    draw.ellipse((px-38, py-55, px+38, py+21), fill=p["accent2"]+(255,))
    draw.polygon([(px-24, py+6), (px+24, py+6), (px, py+62)], fill=p["accent2"]+(255,))
    draw.ellipse((px-13, py-30, px+13, py-4), fill=(255,255,255,230))
    # camera
    _rounded(draw, (int(w*0.31), int(h*0.66), int(w*0.69), int(h*0.84)), 34, p["dark"]+(230,), None)
    draw.rectangle((int(w*0.39), int(h*0.62), int(w*0.52), int(h*0.67)), fill=p["dark"]+(230,))
    draw.ellipse((int(w*0.43), int(h*0.69), int(w*0.57), int(h*0.78)), fill=(255,255,255,230))
    draw.ellipse((int(w*0.46), int(h*0.71), int(w*0.54), int(h*0.76)), fill=p["accent2"]+(240,))


def _draw_dm(draw, w, h, p):
    # phone
    _rounded(draw, (int(w*0.24), int(h*0.14), int(w*0.76), int(h*0.84)), 58, p["dark"]+(245,), None)
    _rounded(draw, (int(w*0.28), int(h*0.19), int(w*0.72), int(h*0.79)), 42, (255,255,255,238), None)
    # chat bubbles
    _rounded(draw, (int(w*0.33), int(h*0.27), int(w*0.62), int(h*0.34)), 28, p["accent2"]+(230,), None)
    _rounded(draw, (int(w*0.42), int(h*0.40), int(w*0.67), int(h*0.47)), 28, p["accent"]+(235,), None)
    _rounded(draw, (int(w*0.33), int(h*0.54), int(w*0.64), int(h*0.61)), 28, p["accent2"]+(210,), None)
    _rounded(draw, (int(w*0.45), int(h*0.67), int(w*0.66), int(h*0.73)), 24, p["accent"]+(225,), None)
    for y in [0.295, 0.43, 0.57, 0.70]:
        draw.ellipse((int(w*0.36), int(h*y), int(w*0.38), int(h*y)+20), fill=(255,255,255,130))


def _draw_school(draw, w, h, p):
    # board
    _rounded(draw, (int(w*0.10), int(h*0.15), int(w*0.90), int(h*0.43)), 36, p["dark"]+(230,), (255,255,255,120), 3)
    # chalk lines
    for i, frac in enumerate([0.22, 0.28, 0.34]):
        draw.line((int(w*0.20), int(h*frac), int(w*(0.80 - i*0.08)), int(h*frac)), fill=(255,255,255,130), width=6)
    # notebook
    _rounded(draw, (int(w*0.21), int(h*0.60), int(w*0.67), int(h*0.84)), 24, p["paper"]+(240,), None)
    for x in range(int(w*0.26), int(w*0.64), int(w*0.055)):
        draw.line((x, int(h*0.61), x, int(h*0.83)), fill=(120,130,160,60), width=2)
    for y in range(int(h*0.65), int(h*0.82), int(h*0.035)):
        draw.line((int(w*0.25), y, int(w*0.64), y), fill=(120,130,160,65), width=2)
    # pencil
    draw.polygon([(int(w*0.66), int(h*0.63)), (int(w*0.86), int(h*0.75)), (int(w*0.82), int(h*0.80)), (int(w*0.62), int(h*0.68))], fill=p["accent"]+(245,))
    draw.polygon([(int(w*0.86), int(h*0.75)), (int(w*0.91), int(h*0.78)), (int(w*0.82), int(h*0.80))], fill=p["dark"]+(230,))


def _draw_food(draw, w, h, p):
    # plate
    draw.ellipse((int(w*0.18), int(h*0.60), int(w*0.82), int(h*0.86)), fill=(255,255,255,235))
    draw.ellipse((int(w*0.27), int(h*0.65), int(w*0.73), int(h*0.81)), fill=(255,236,206,235))
    # food blobs
    draw.ellipse((int(w*0.36), int(h*0.66), int(w*0.56), int(h*0.77)), fill=p["accent2"]+(230,))
    draw.ellipse((int(w*0.49), int(h*0.65), int(w*0.66), int(h*0.76)), fill=p["accent"]+(230,))
    draw.ellipse((int(w*0.29), int(h*0.69), int(w*0.43), int(h*0.78)), fill=(110, 190, 120, 230))
    # fork/spoon
    draw.line((int(w*0.13), int(h*0.55), int(w*0.24), int(h*0.86)), fill=(255,255,255,210), width=8)
    draw.line((int(w*0.87), int(h*0.55), int(w*0.76), int(h*0.86)), fill=(255,255,255,210), width=8)


def _draw_language(draw, w, h, p):
    cards = [
        (0.14, 0.18, 0.40, 0.36, "A"),
        (0.58, 0.21, 0.84, 0.39, "あ"),
        (0.18, 0.64, 0.44, 0.82, "¡"),
        (0.56, 0.62, 0.82, 0.80, "你"),
    ]
    for x1,y1,x2,y2,txt in cards:
        _rounded(draw, (int(w*x1), int(h*y1), int(w*x2), int(h*y2)), 34, p["paper"]+(180,), (255,255,255,160), 3)
        try:
            font = get_safe_font("ja" if txt in ["あ", "你"] else "en", int(h*0.07))
            bbox = draw.textbbox((0,0), txt, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            draw.text((int(w*(x1+x2)/2 - tw/2), int(h*(y1+y2)/2 - th/2)), txt, font=font, fill=p["dark"]+(235,))
        except Exception:
            pass


def make_illustration_background(topic: str, cfg: VideoConfig, idx: int, total: int) -> Image.Image:
    """
    레퍼런스 사진처럼 깔끔한 카드형 교육 화면.
    언어 문자 박스와 주제별 오브젝트는 전부 제거하고,
    흰색/연회색 + 메인 파랑 1색 + 검정만 사용합니다.
    """
    w, h = cfg.size
    p = PALETTES["clean"]
    img = _gradient((w, h), p["top"], p["bottom"])

    _draw_soft_blob(
        img,
        (int(w * 0.03), int(h * 0.16), int(w * 0.97), int(h * 0.80)),
        (255, 255, 255, 130),
        blur=90,
    )

    draw = ImageDraw.Draw(img, "RGBA")

    # 메인 표현 카드
    card_x1 = int(w * 0.075)
    card_x2 = int(w * 0.925)
    card_y1 = int(h * 0.345)
    card_y2 = int(h * 0.675)

    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle(
        (card_x1, card_y1 + int(h * 0.010), card_x2, card_y2 + int(h * 0.010)),
        radius=int(w * 0.055),
        fill=(0, 0, 0, 26),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle(
        (card_x1, card_y1, card_x2, card_y2),
        radius=int(w * 0.055),
        fill=(255, 255, 255, 246),
        outline=(235, 240, 250, 180),
        width=2,
    )

    # 하단 파란 웨이브
    accent = p["accent"] + (255,)
    wave = [
        (0, h),
        (0, int(h * 0.965)),
        (int(w * 0.20), int(h * 0.940)),
        (int(w * 0.38), int(h * 0.915)),
        (int(w * 0.58), int(h * 0.920)),
        (int(w * 0.78), int(h * 0.895)),
        (w, int(h * 0.780)),
        (w, h),
    ]
    draw.polygon(wave, fill=accent)

    return img


# --------------------------------------------------------------------------- #
# 브랜딩 오버레이 / 인트로
# --------------------------------------------------------------------------- #
def make_brand_badge_clip(cfg: VideoConfig, duration: float):
    w, h = cfg.size
    card_w = int(w * 0.17)
    card_h = int(h * 0.06)
    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle((0, 0, card_w-1, card_h-1), radius=int(card_h*0.34), fill=(255,255,255,230), outline=(255,255,255,250), width=2)
    logo_font = get_safe_font("en", int(card_h * 0.42))
    name_font = get_safe_font("en", int(card_h * 0.25))
    draw.ellipse((int(card_w*0.08), int(card_h*0.18), int(card_w*0.34), int(card_h*0.82)), fill=(122,162,255,255))
    lbox = draw.textbbox((0, 0), cfg.logo_text, font=logo_font)
    lw = lbox[2] - lbox[0]
    lh = lbox[3] - lbox[1]
    draw.text((int(card_w*0.21 - lw/2), int(card_h*0.50 - lh/2)), cfg.logo_text, font=logo_font, fill=(255,255,255,255))
    draw.text((int(card_w*0.39), int(card_h*0.23)), cfg.brand_name, font=name_font, fill=(40,55,88,255))
    draw.text((int(card_w*0.39), int(card_h*0.50)), "LANGUAGE SHORTS", font=name_font, fill=(90,105,135,255))
    clip = _with_duration(ImageClip(np.array(img)), duration)
    return _with_position(clip, (int(w*0.055), int(h*0.04)))


def make_title_box_clip(topic: str, cfg: VideoConfig, duration: float, intro: bool = False):
    w, h = cfg.size
    box_w = int(w * (0.86 if cfg.is_shorts else 0.58))
    box_h = int(h * (0.105 if not intro else 0.13))
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((2, 4, box_w - 2, box_h - 2), radius=int(box_h * 0.38), fill=(0, 0, 0, 20))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle(
        (0, 0, box_w - 1, box_h - 1),
        radius=int(box_h * 0.38),
        fill=(255, 255, 255, 236),
        outline=(225, 231, 242, 210),
        width=2,
    )

    accent = (35, 84, 190, 255)
    dark = (32, 36, 44, 255)
    muted = (74, 86, 110, 255)

    draw.rounded_rectangle(
        (int(box_w * 0.045), int(box_h * 0.22), int(box_w * 0.057), int(box_h * 0.78)),
        radius=5,
        fill=accent,
    )

    label_font = get_safe_font("ko", int(box_h * 0.20))
    title_font = get_safe_font("ko", int(box_h * 0.25))

    topic_text = topic if len(topic) <= 18 else topic[:18] + "…"
    draw.text((int(box_w * 0.10), int(box_h * 0.22)), cfg.title_label, font=label_font, fill=muted)
    draw.text((int(box_w * 0.10), int(box_h * 0.50)), topic_text, font=title_font, fill=dark)

    clip = _with_duration(ImageClip(np.array(img)), duration)
    x = int((w - box_w) / 2)
    y = int(h * (0.055 if not intro else 0.38))
    return _with_position(clip, (x, y))


def make_intro_caption_clip(cfg: VideoConfig, duration: float):
    text = "오늘 바로 써먹는 외국어 표현"
    clip = make_text_image_clip(
        text=text,
        lang="en",
        font_size=30 if cfg.is_shorts else 34,
        color=(245,245,245,255),
        video_size=cfg.size,
        max_width_ratio=0.7,
        duration=duration,
        stroke_width=2,
    )
    return _with_position(clip, ("center", int(cfg.size[1] * 0.53)))


def make_intro_clip(topic: str, cfg: VideoConfig, bg_source=None):
    duration = max(0.8, float(cfg.intro_duration))
    bg = build_background_layer(bg_source, cfg, duration, topic=topic, idx=-1, total=1)
    title = make_title_box_clip(topic, cfg, duration, intro=True)
    caption = make_intro_caption_clip(cfg, duration)
    intro = CompositeVideoClip([bg, title, caption], size=cfg.size)
    return _with_duration(intro, duration)


# --------------------------------------------------------------------------- #
# 배경
# --------------------------------------------------------------------------- #
def _cover_resize_crop(clip, target_size: Tuple[int, int]):
    tw, th = target_size
    scale = max(tw / clip.w, th / clip.h)
    clip = _resize(clip, (int(clip.w * scale) + 2, int(clip.h * scale) + 2))
    return _crop(clip, x_center=clip.w / 2, y_center=clip.h / 2, width=tw, height=th)


def load_bg_source(cfg: VideoConfig):
    if not cfg.bg_video_path:
        return None

    path = Path(cfg.bg_video_path)
    if not path.exists():
        return None

    try:
        clip = VideoFileClip(str(path))
        clip = _without_audio(clip)
        return _cover_resize_crop(clip, cfg.size)
    except Exception as e:
        log.warning("배경 영상 실패: %s", e)
        return None


def build_background_layer(bg_source, cfg: VideoConfig, duration: float, topic: str, idx: int, total: int):
    if bg_source is not None:
        try:
            clip = bg_source
            if clip.duration < duration:
                clip = _loop_to_duration(clip, duration)
            clip = _subclip(clip, 0, duration)
            return _with_duration(clip, duration)
        except Exception:
            pass

    if cfg.use_illustration_bg:
        img = make_illustration_background(topic, cfg, idx, total)
        return _with_duration(ImageClip(np.array(img)), duration)

    return ColorClip(size=cfg.size, color=(26, 26, 30), duration=duration)


def add_background_music(final_video, cfg: VideoConfig):
    if not cfg.bgm_path:
        return final_video

    path = Path(cfg.bgm_path)
    if not path.exists():
        return final_video

    try:
        bgm = AudioFileClip(str(path))
        duration = final_video.duration
        if bgm.duration < duration:
            loops = math.ceil(duration / max(bgm.duration, 0.1))
            bgm = concatenate_audioclips([bgm] * loops)
        bgm = _subclip(bgm, 0, duration)
        bgm = _with_start(_scale_volume(bgm, cfg.bgm_volume), 0)

        mixed = CompositeAudioClip([final_video.audio, bgm]) if final_video.audio else CompositeAudioClip([bgm])
        mixed = _with_duration(mixed, duration)
        return _with_audio(final_video, mixed)
    except Exception as e:
        log.warning("BGM 실패: %s", e)
        return final_video


# --------------------------------------------------------------------------- #
# 생성
# --------------------------------------------------------------------------- #
def build_word_segment(
    topic: str,
    item: Dict[str, str],
    cfg: VideoConfig,
    tmp_dir: Path,
    idx: int,
    total: int,
    bg_source=None,
):
    kr_path = tmp_dir / f"kr_{idx}.mp3"
    target_path = tmp_dir / f"target_{idx}.mp3"

    free_tts_to_file(item["kr"], cfg.source_lang, kr_path, cfg.slow_tts, cfg.use_tts)
    free_tts_to_file(item["target"], cfg.target_lang, target_path, cfg.slow_tts, cfg.use_tts)

    audio_kr = AudioFileClip(str(kr_path))
    audio_target = AudioFileClip(str(target_path))

    start_target1 = audio_kr.duration + cfg.gap_after_kr
    start_target2 = start_target1 + audio_target.duration + cfg.shadowing_pause
    total_duration = start_target2 + audio_target.duration + cfg.tail_padding

    combined_audio = CompositeAudioClip(
        [
            _with_start(audio_kr, 0),
            _with_start(audio_target, start_target1),
            _with_start(audio_target, start_target2),
        ]
    )
    combined_audio = _with_duration(combined_audio, total_duration)

    bg = build_background_layer(bg_source, cfg, total_duration, topic=topic, idx=idx, total=total)

    kr_clip = make_text_image_clip(
        item["kr"],
        lang=cfg.source_lang,
        font_size=cfg.kr_font_size,
        color=(32, 36, 44, 255),
        video_size=cfg.size,
        max_width_ratio=0.82,
        duration=total_duration,
        stroke_width=0,
    )

    target_clip = make_text_image_clip(
        item["target"],
        lang=cfg.target_lang,
        font_size=cfg.target_font_size,
        color=(35, 84, 190, 255),
        video_size=cfg.size,
        max_width_ratio=0.78,
        duration=total_duration,
        stroke_width=0,
    )

    tip_clip = make_text_image_clip(
        item.get("tip") or "소리 내서 따라 해보세요",
        lang=cfg.source_lang,
        font_size=cfg.tip_font_size,
        color=(32, 36, 44, 255),
        video_size=cfg.size,
        max_width_ratio=0.78,
        duration=total_duration,
        stroke_width=0,
    )

    kr_pos, target_pos, tip_pos = layout_text_block(kr_clip, target_clip, tip_clip, cfg.size)
    kr_in = 0.08
    target_in = 0.20
    tip_in = 0.34
    kr_clip = _with_start(_with_duration(_with_position(kr_clip, kr_pos), max(0.1, total_duration - kr_in)), kr_in)
    target_clip = _with_start(_with_duration(_with_position(target_clip, target_pos), max(0.1, total_duration - target_in)), target_in)
    tip_clip = _with_start(_with_duration(_with_position(tip_clip, tip_pos), max(0.1, total_duration - tip_in)), tip_in)
    progress_clip = make_progress_clip(idx, total, cfg, total_duration)
    title_box_clip = make_title_box_clip(topic, cfg, total_duration, intro=False)

    segment = CompositeVideoClip([bg, title_box_clip, progress_clip, kr_clip, target_clip, tip_clip], size=cfg.size)
    segment = _with_audio(segment, combined_audio)

    return segment, [audio_kr, audio_target]


def create_study_video(
    topic: str,
    items: List[Dict[str, str]],
    cfg: VideoConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    def progress(message: str):
        log.info(message)
        if progress_callback:
            progress_callback(message)

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(exist_ok=True)

    suffix = "shorts" if cfg.is_shorts else "long"
    output_path = cfg.output_dir / f"{safe_filename(topic)}_{cfg.target_lang}_clean_intro_{suffix}.mp4"

    bg_source = load_bg_source(cfg)
    video_clips = []
    audio_handles = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        total = len(items)

        progress("0/3 인트로 카드 생성 중")
        intro_clip = make_intro_clip(topic, cfg, bg_source=bg_source)
        video_clips.append(intro_clip)

        for idx, item in enumerate(items):
            progress(f"1/3 음성/자막/일러스트 생성 중: {idx + 1}/{total} - {item['kr']} → {item['target']}")
            segment, handles = build_word_segment(topic, item, cfg, tmp_dir, idx, total, bg_source=bg_source)
            video_clips.append(segment)
            audio_handles.extend(handles)

        if not video_clips:
            raise RuntimeError("생성 가능한 영상 클립이 없습니다.")

        progress("2/3 클립 병합 및 BGM 처리 중")
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video = add_background_music(final_video, cfg)

        progress("3/3 mp4 렌더링 중")
        final_video.write_videofile(
            str(output_path),
            fps=20,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            logger=None,
        )

        final_video.close()

        for clip in video_clips:
            try:
                clip.close()
            except Exception:
                pass
        for handle in audio_handles:
            try:
                handle.close()
            except Exception:
                pass

    if bg_source is not None:
        try:
            bg_source.close()
        except Exception:
            pass

    progress(f"완료: {output_path}")
    return output_path
