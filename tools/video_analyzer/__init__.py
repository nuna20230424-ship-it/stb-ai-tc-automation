"""video_analyzer — 임의 영상(시나리오 무관) 오류 분석 파이프라인.

기존 TC 자동화는 `시나리오 expected ↔ 캡처 프레임` 비교 구조라 사전 정의가 필수.
이 모듈은 정반대로 **사전 정의 없이** 영상 자체에서 STB 운영 이상을 자동 검출.

검출 카테고리 (결정론):
  - black_frame : 블랙 아웃 (평균 휘도 < 임계, 연속 N 프레임)
  - freeze      : 프리즈 (연속 프레임 픽셀 차이 < 임계)
  - no_signal   : 신호 없음 (단일 색상 / 표준편차 매우 낮음)
  - scene_jump  : 비정상 장면 전환 (히스토그램 거리 폭증)

선택적 보강 (vision LLM 호출):
  - suspicious 프레임에 한해 embedding-mcp /vision/describe 호출
  - 묘사 텍스트에 "error / 오류 / loading / ..." 키워드 매칭 시 incident 보강

흐름:
  analyze_video(path) → frames(샘플링) → detectors(...) → incidents[] + timeline
"""
