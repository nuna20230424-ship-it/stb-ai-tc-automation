"""rdk — RDK Thunder/WPEFramework JSON-RPC 폴백 (Phase 5).

Comcast/Sky RDK 박스는 Thunder(WPEFramework) JSON-RPC로 키 주입·앱 제어 API를 노출.
IR-only 의존을 완화: RDKShell.injectKey API로 결정론적 입력 (IR 사각/광원 간섭 회피).

transport를 주입 가능하게 설계 → 실 박스 없이 단위 테스트 가능.
"""
