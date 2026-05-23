# 07. Test Server를 Mac mini M4 Pro로 대체 검토

> 2026-05-23 추가. 사내 안정성 랙에서 이미 운용 중인 Mac mini M4 Pro를 Test Server로 활용 가능한지 호환성·성능·리스크 평가.

## 결론

**✅ 대체 가능. 일부 영역(로컬 LLM/임베딩, 전력 효율)은 오히려 유리.**  
PoC BOM에서 **Test Server 250만원 절감 → 약 670만원 → 420만원**으로 시작 가능. 단, USB 허브와 일부 운영 정책에서 약간의 보완 필요.

---

## 1. 호환성 매트릭스

| 컴포넌트 | macOS / Apple Silicon | 비고 |
|---|---|---|
| **Magewell USB Capture 4K Plus** | ✅ Plug & Play | UVC 표준, macOS 공식 지원 |
| **Elgato Cam Link 4K** | ✅ | macOS 공식 지원 |
| **Global Caché iTach IP2IR** | ✅ | LAN 기반이라 OS 무관 |
| **Shelly Smart Plug** | ✅ | HTTP API |
| **FTDI USB-UART** | ✅ | macOS 드라이버 |
| **ADB (Android TV)** | ✅ | Homebrew 설치 |
| **Docker Desktop (Apple Silicon)** | ✅ | ARM64 native 이미지 우선 |
| **Qdrant / InfluxDB / MinIO / Grafana** | ✅ | 모두 ARM64 공식 이미지 |
| **FFmpeg / GStreamer** | ✅ | Homebrew |
| **Pytest / Playwright** | ✅ | |
| **PyTorch (MPS backend)** | ✅ | NVIDIA CUDA는 불가, **Metal/MPS로 대체** |
| **MLX / CoreML / Apple Neural Engine** | ✅ ⚡ | Apple Silicon 전용 — **로컬 LLM·임베딩에 매우 유리** |
| **Ollama (로컬 LLM)** | ✅ ⚡ | M4 Pro에서 매우 빠름 |
| **GitHub Actions self-hosted runner** | ✅ | macOS runner 공식 지원 |
| **LIRC (USB IR)** | ❌ Linux 전용 | **iTach LAN 방식으로 우회** (이미 BOM 채택) |
| **CUDA / NVIDIA 전용 라이브러리** | ❌ | MPS/MLX 대안 충분, 대규모 학습은 외부 GPU로 분리 |

## 2. M4 Pro의 강점 (생각보다 큼)

1. **Apple Neural Engine + 16/20-core GPU** — Ollama, MLX 기반 로컬 LLM/임베딩이 매우 빠름. **소형 Vision 모델은 Gemini API 호출 없이 로컬 추론 가능 → API 비용 절감**
2. **Unified Memory (최대 64GB)** — CPU/GPU 메모리 공유, 큰 모델 로딩 유리
3. **저전력·정숙** — 24/7 운영 시 전기료·소음 유리
4. **이미 안정성 랙에서 운용 중** → 신뢰성·운영 노하우 검증됨

## 3. 보완 필요 사항

| 항목 | 이슈 | 해결 방법 |
|---|---|---|
| **USB 포트 수** | Mac mini M4 Pro: TB5×3, USB-A×2 | **Powered Thunderbolt 4/5 허브** 추가 (~15만원). 캡처카드 다수 연결용 |
| **Docker x86 이미지** | x86 이미지는 Rosetta 에뮬레이션 → 성능 저하 | ARM64 이미지로 통일 (대부분 가능). 어쩔 수 없을 때만 `platform: linux/amd64` |
| **LIRC 미지원** | macOS에서 LIRC 사용 불가 | **iTach IP2IR (LAN)** 사용 — 이미 BOM에 포함된 선택. 자연스러운 대안 |
| **대규모 모델 학습** | M4 Pro는 추론용. 대규모 fine-tune은 CUDA 환경이 효율적 | Sprint 3에서 필요 시 **클라우드 GPU(AWS g5, Lambda, Vast.ai)** 임시 분리 사용 |
| **랙 마운트** | Mac mini는 1U 마운트 키트 필요 | **Sonnet xMac Mini Server** 또는 **HD Plex H1.S.O.D.A** 등 마운트 키트 |
| **PCIe 캡처카드** | Mac mini는 PCIe 슬롯 없음 | **USB 캡처카드(Magewell USB)** 또는 **Thunderbolt 캡처(Magewell Pro Capture HDMI 4K via TB)** 사용 |

## 4. 권장 구성 (Mac mini M4 Pro 기반)

```
┌──────────────────────────────────────────────────────────────────┐
│                  Mac mini M4 Pro (랙 마운트)                       │
│  ─────────────────────────────────────────────────────────────  │
│  macOS Sequoia + Docker Desktop (Apple Silicon)                   │
│                                                                  │
│  로컬 추론:  Ollama / MLX (Vision + 텍스트 임베딩)                 │
│  컨테이너:   Qdrant / InfluxDB / MinIO / Grafana (ARM64)          │
│  서비스:    Capture/IR/Power/Log 데몬                            │
│  CI:       GitHub Actions self-hosted runner (macOS)             │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼ Thunderbolt 5
   ┌─────────────────────────────┐
   │  Powered TB4/TB5 Dock       │
   │  - USB-A × 4 (캡처카드용)    │
   │  - Ethernet 2.5/10GbE       │
   │  - SD card 등                │
   └──────────┬──────────────────┘
              │ USB
   ┌──────────▼──────────┐
   │  Magewell Capture × 2~4│
   └────────────────────┘
```

## 5. 수정된 PoC BOM (Mac mini 활용 시)

| 분류 | 변경 | 금액 영향 |
|---|---|---|
| ~~Ryzen Test Server~~ | **Mac mini M4 Pro (기존 자산)** | **-250만원** |
| Thunderbolt 4/5 Dock 추가 | OWC TB4 Dock 등 | **+15만원** |
| 1U 랙 마운트 키트 | Sonnet xMac mini Server 등 | **+10만원** |
| **순 절감** | | **약 -225만원** |

**총 PoC 예산: 약 445만원** (기존 670만원 대비 225만원 절감)

## 6. 검증 필요 항목 (Sprint 0 첫 주에 수행)

- [ ] Mac mini에서 Magewell USB Capture 인식 확인 (단순 `ffmpeg -f avfoundation -list_devices true`)
- [ ] Docker Desktop으로 Qdrant/InfluxDB/MinIO 컨테이너 정상 구동
- [ ] iTach IP2IR REST API 호출 정상 동작
- [ ] FTDI USB-UART에서 STB 시리얼 로그 수신 (`screen /dev/cu.usbserial-*`)
- [ ] Shelly Plug HTTP API로 전원 ON/OFF
- [ ] Ollama로 로컬 Vision 모델(예: Llama 3.2 Vision) 추론 속도 측정
- [ ] 4시간 연속 캡처 + 임베딩 생성 시 발열/성능 안정성

## 7. 권고 의사결정

| 옵션 | 추천도 |
|---|---|
| **Mac mini M4 Pro로 PoC 시작 (권장)** | ⭐⭐⭐⭐⭐ — 225만원 절감, 자산 활용, 로컬 LLM 강점 |
| 별도 Linux 서버 신규 구입 | ⭐⭐ — 예산 부담, M4의 Neural Engine 이점 포기 |
| 하이브리드: Mac mini(추론) + 기존 사내 Linux(데이터 저장) | ⭐⭐⭐⭐ — Sprint 2 이후 확장 시 고려 |

## 8. 주의: 다음 시나리오엔 Linux 서버 별도 필요할 수 있음

- 대규모 CUDA 전용 라이브러리 사용 (예: TensorRT, NVIDIA NIM)
- 5대 이상의 캡처카드 동시 운영 (USB 대역폭 한계)
- 멀티 GPU 학습 (대규모 fine-tune)
- 사내 보안 정책상 macOS가 인프라 서버로 허용되지 않는 경우

→ 위 시나리오에 해당하면 Sprint 2~3에서 Linux 서버 추가 도입 검토
