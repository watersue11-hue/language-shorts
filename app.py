from __future__ import annotations

from pathlib import Path
import traceback

import streamlit as st


st.set_page_config(
    page_title="무료 다국어 학습 숏츠 생성기",
    page_icon="🎬",
    layout="centered",
)

FIXED_ILLUSTRATION_STYLE = "clean"

LANG_OPTIONS = {
    "스페인어": "es",
    "영어": "en",
    "일본어": "ja",
    "중국어": "zh",
    "프랑스어": "fr",
    "독일어": "de",
    "이탈리아어": "it",
}

LANG_DISPLAY_NAMES = {
    "ko": "한국어",
    "es": "스페인어",
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "fr": "프랑스어",
    "de": "독일어",
    "it": "이탈리아어",
}


def safe_import_generator():
    """
    Streamlit Cloud에서 moviepy/gTTS/PIL import가 실패하면
    앱 전체가 빈 화면이 되는 것을 막기 위해 버튼 클릭 이후에만 import합니다.
    """
    try:
        from free_video_generator import (
            VideoConfig,
            create_study_video,
            get_free_script,
            parse_manual_items,
        )
        return VideoConfig, create_study_video, get_free_script, parse_manual_items, None
    except Exception as e:
        return None, None, None, None, e


def fallback_manual_items(text: str):
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


def fallback_script(target_lang: str, n: int):
    data = {
        "es": [
            {"kr": "안녕하세요", "target": "Hola", "tip": "기본 인사"},
            {"kr": "감사합니다", "target": "Gracias", "tip": "고마울 때 사용"},
            {"kr": "실례합니다", "target": "Disculpe", "tip": "말 걸 때 사용"},
            {"kr": "얼마예요?", "target": "¿Cuánto cuesta?", "tip": "가격 질문"},
            {"kr": "다시 말해 주세요", "target": "Repítalo, por favor", "tip": "못 들었을 때"},
        ],
        "en": [
            {"kr": "안녕하세요", "target": "Hello", "tip": "기본 인사"},
            {"kr": "감사합니다", "target": "Thank you", "tip": "고마울 때 사용"},
            {"kr": "실례합니다", "target": "Excuse me", "tip": "말 걸 때 사용"},
            {"kr": "얼마예요?", "target": "How much is it?", "tip": "가격 질문"},
            {"kr": "다시 말해 주세요", "target": "Could you say that again?", "tip": "못 들었을 때"},
        ],
        "ja": [
            {"kr": "안녕하세요", "target": "こんにちは", "tip": "기본 인사"},
            {"kr": "감사합니다", "target": "ありがとうございます", "tip": "고마울 때 사용"},
            {"kr": "실례합니다", "target": "すみません", "tip": "말 걸 때 사용"},
            {"kr": "얼마예요?", "target": "いくらですか？", "tip": "가격 질문"},
            {"kr": "다시 말해 주세요", "target": "もう一度言ってください", "tip": "못 들었을 때"},
        ],
        "zh": [
            {"kr": "안녕하세요", "target": "你好", "tip": "기본 인사"},
            {"kr": "감사합니다", "target": "谢谢", "tip": "고마울 때 사용"},
            {"kr": "실례합니다", "target": "打扰一下", "tip": "말 걸 때 사용"},
            {"kr": "얼마예요?", "target": "多少钱？", "tip": "가격 질문"},
            {"kr": "다시 말해 주세요", "target": "请再说一遍", "tip": "못 들었을 때"},
        ],
    }
    base = data.get(target_lang, data["en"])
    if not base:
        return []
    out = []
    for i in range(n):
        item = dict(base[i % len(base)])
        out.append(item)
    return out


st.title("🎬 무료 다국어 학습 숏츠 생성기")
st.caption("무료 내장 표현/직접 입력 + 무료 gTTS 음성 + 깔끔한 교육용 일러스트 배경 + 고정 인트로로 mp4를 만듭니다.")
st.success("앱 첫 화면 로드 완료")

with st.expander("이 버전 특징", expanded=False):
    st.markdown(
        """
        - OpenAI API를 사용하지 않습니다.
        - API Key 입력칸도 없습니다.
        - 브랜드명과 로고 텍스트는 제거했습니다.
        - 1초 인트로 카드와 고정 제목 박스는 유지합니다.
        - 첫 화면 빈 화면 방지를 위해 무거운 영상 생성 모듈은 버튼 클릭 후 불러옵니다.
        """
    )

with st.sidebar:
    st.header("영상 설정")

    selected_lang_name = st.selectbox("학습 언어", list(LANG_OPTIONS.keys()), index=0)
    target_lang = LANG_OPTIONS[selected_lang_name]

    is_shorts = st.radio("영상 비율", ["쇼츠 9:16", "롱폼 16:9"], index=0) == "쇼츠 9:16"

    max_words = 10 if is_shorts else 50
    default_words = 5 if is_shorts else 10
    words = st.slider("표현 개수", min_value=1, max_value=max_words, value=default_words, step=1)
    if is_shorts:
        st.caption("쇼츠는 1~10개까지 선택 가능합니다.")
    else:
        st.caption("롱폼은 1~50개까지 선택 가능합니다. 20개 이상은 렌더링 시간이 길어질 수 있습니다.")

    shadowing_pause = st.slider("따라 말하기 간격", 1.0, 5.0, 2.2, 0.5)

    st.divider()
    st.header("음성 설정")

    use_tts = st.checkbox("무료 TTS 사용", value=True)
    slow_tts = st.checkbox("천천히 말하기", value=False)

    st.divider()
    st.header("배경 설정")

    use_illustration_bg = st.checkbox(
        "고정 일러스트 배경 사용",
        value=True,
        help="깔끔한 교육용 스타일로 고정된 배경입니다.",
    )

    st.info("현재 그림체: 흰색 + 검정 + 파랑 메인색 1개 (고정)")
    st.info("고정 요소: 1초 인트로 / 고정 제목 박스 / 같은 자막 등장감")

    use_bgm = st.checkbox("BGM 사용", value=Path("assets/bgm.mp3").exists())
    bgm_volume = st.slider("BGM 볼륨", 0.0, 0.25, 0.07, 0.01)

    use_bg_video = st.checkbox(
        "내 배경 영상 사용",
        value=Path("assets/bg_loop.mp4").exists(),
        help="assets/bg_loop.mp4가 있으면 일러스트 배경보다 우선 적용됩니다.",
    )

st.subheader("콘텐츠 입력")

topic = st.text_input(
    "영상 주제",
    placeholder="예: 공항, 카페, 여행, 학교, 음식점, DM, 기본 회화",
)

source_mode = st.radio(
    "대본 방식",
    ["무료 내장 표현 자동 선택", "직접 입력"],
    horizontal=True,
)

items = []

if source_mode == "무료 내장 표현 자동 선택":
    if topic:
        _, _, get_free_script, _, import_error = safe_import_generator()
        if import_error is None:
            items = get_free_script(topic, target_lang, words)
        else:
            items = fallback_script(target_lang, words)
            st.warning("영상 생성 모듈 import 전이라 기본 미리보기만 표시합니다. 생성 버튼을 누르면 오류를 자세히 표시합니다.")

        st.markdown("#### 생성될 표현 미리보기")
        st.table(items)
    else:
        st.info("주제를 입력하면 표현 미리보기가 표시됩니다.")

else:
    st.markdown(
        """
        아래 형식으로 입력하세요.

        ```txt
        한국어 뜻 | 외국어 표현 | 짧은 설명
        안녕하세요 | Hola | 기본 인사
        감사합니다 | Gracias | 고마울 때 사용
        ```
        """
    )

    default_target = {
        "es": "Hola",
        "en": "Hello",
        "ja": "こんにちは",
        "zh": "你好",
        "fr": "Bonjour",
        "de": "Hallo",
        "it": "Ciao",
    }.get(target_lang, "Hello")

    default_thanks = {
        "es": "Gracias",
        "en": "Thank you",
        "ja": "ありがとうございます",
        "zh": "谢谢",
        "fr": "Merci",
        "de": "Danke",
        "it": "Grazie",
    }.get(target_lang, "Thank you")

    default_manual = f"""안녕하세요 | {default_target} | 기본 인사
감사합니다 | {default_thanks} | 고마울 때 사용
실례합니다 | Excuse me | 말을 걸 때 사용"""
    manual_text = st.text_area("직접 입력", value=default_manual, height=180)

    _, _, _, parse_manual_items, import_error = safe_import_generator()
    if import_error is None:
        items = parse_manual_items(manual_text, target_lang)
    else:
        items = fallback_manual_items(manual_text)

    if items:
        st.markdown("#### 입력된 표현 미리보기")
        st.table(items)

if source_mode == "무료 내장 표현 자동 선택":
    st.caption("자동 선택은 내장 예시를 사용합니다. 많은 개수를 선택하면 일부 표현이 반복될 수 있습니다.")
else:
    st.caption("직접 입력은 줄 수만큼 그대로 반영됩니다. 롱폼 50개 제작은 직접 입력 방식을 권장합니다.")

st.markdown("#### 배경 방식")
if use_bg_video and Path("assets/bg_loop.mp4").exists():
    st.info("assets/bg_loop.mp4를 배경 영상으로 사용합니다.")
elif use_illustration_bg:
    st.info("사진처럼 흰색/검정/파랑만 쓰는 깔끔한 카드형 배경을 사용합니다.")
else:
    st.info("단색 배경으로 제작합니다.")

generate = st.button("🔥 무료로 영상 생성하기", use_container_width=True)

if generate:
    if not topic.strip() and source_mode == "무료 내장 표현 자동 선택":
        st.error("주제를 입력하세요.")
        st.stop()

    if not items:
        st.error("생성할 표현이 없습니다.")
        st.stop()

    VideoConfig, create_study_video, get_free_script, parse_manual_items, import_error = safe_import_generator()

    if import_error is not None:
        st.error("영상 생성 모듈을 불러오지 못했습니다. 아래 오류를 확인하세요.")
        st.code("".join(traceback.format_exception(type(import_error), import_error, import_error.__traceback__)))
        st.stop()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    cfg = VideoConfig(
        is_shorts=is_shorts,
        shadowing_pause=float(shadowing_pause),
        words_per_topic=int(words),
        output_dir=output_dir,
        target_lang=target_lang,
        use_tts=use_tts,
        slow_tts=slow_tts,
        use_illustration_bg=use_illustration_bg,
        illustration_style=FIXED_ILLUSTRATION_STYLE,
        bgm_path="assets/bgm.mp3" if use_bgm else None,
        bgm_volume=float(bgm_volume),
        bg_video_path="assets/bg_loop.mp4" if use_bg_video else None,
    )

    progress_box = st.empty()

    def ui_progress(message: str):
        progress_box.info(message)

    with st.status("영상 생성 중", expanded=True) as status:
        try:
            output_path = create_study_video(
                topic=topic.strip() or "manual",
                items=items[:words],
                cfg=cfg,
                progress_callback=ui_progress,
            )
            status.update(label="영상 생성 완료", state="complete", expanded=False)

            st.success("완성됐습니다.")
            st.subheader("미리보기")
            st.video(str(output_path))

            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 mp4 다운로드",
                    data=f,
                    file_name=output_path.name,
                    mime="video/mp4",
                    use_container_width=True,
                )

        except Exception as e:
            status.update(label="영상 생성 실패", state="error", expanded=True)
            st.exception(e)
            st.error("오류가 났습니다. 그래도 유료 API 비용은 발생하지 않습니다.")
