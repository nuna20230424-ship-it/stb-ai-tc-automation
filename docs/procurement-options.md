# STB AI 자동화 — 장비 구매 옵션 (최적 vs 최소비용)

> **검증 일자**: 2026-05-29 (제조사 공식 + 글로벌 리테일러 5개사 교차 확인)
> **환산**: USD → KRW는 ₩1,350/USD 기준 참고치. 해외 배송·관세·부가세 별도.
> **제외**: Test Server(사내 자산 Mac mini M4 Pro = 0원), 운영 노트북, SaaS, 외부 LLM 키.

두 가지 시나리오 — **목적에 맞춰 선택**:

| 시나리오 | 합계 | 커버 범위 |
|---|---|---|
| 🏆 **최적 효과** (Sprint 1~2 전면) | 약 **$1,350 (₩182만)** 핵심 + 확장 $2,154 | 200 시나리오 전체 (음성·BT·anomaly·24/7 무인) |
| 💰 **최소비용 최대효과** (PoC 가치 증명) | 약 **$401 (₩54만)** | 채널 Zap E2E 1대로 자동화 동작 시연 |

---

# 🏆 최적 효과 — Sprint 1~2 전면 자동화

> **목표**: 200 시나리오 카탈로그 전부를 24/7 자동 회귀 가능. 음성·BT·anomaly 시나리오 포함.

## Tier 1: 핵심 — 약 $1,350 (₩182만)

| # | 품목 | 모델 (검증) | 수량 | 단가 | 소계 | 공식 / 구매 |
|---|---|---|---|---|---|---|
| 1 | HDMI 캡처카드 | **Magewell USB Capture HDMI 4K Plus** (32090) | 2 | $320 | $640 | [magewell.com](https://www.magewell.com/products/usb-capture-hdmi-4k-plus) · [Amazon](https://www.amazon.com/Magewell-USB-Capture-HDMI-Plus/dp/B0754C5XLW) · [B&H](https://www.bhphotovideo.com/c/product/1358688-REG/magewell_32090_usb_3_0_dongle_1_channel.html) |
| 2 | IR 송신·학습 | **BroadLink RM4 Mini** (Wi-Fi, 학습+송신) | 1 | $26 | $26 | [ebroadlink.com](https://ebroadlink.com/products/broadlink-rm4-mini-universal-remote-wi-fi-ir-control-hub_certified-wwa-work-with-alexa_-black) · [Amazon](https://www.amazon.com/Broadlink-RM4-Universal-Control-Compatible/dp/B07ZSF46BX) |
| 3 | 관리형 스위치 | **TP-Link TL-SG3210** (8 GbE + 2 SFP, L2+) | 1 | $140 | $140 | [tp-link.com](https://www.tp-link.com/us//service-provider/managed-switch/tl-sg3210/) · [Newegg](https://www.newegg.com/tp-link-tl-sg3210-8-x-rj45-2-x-sfp/p/N82E16833704092) |
| 4 | HDMI 분배기 1×2 | 4K HDR · HDCP 2.2 (commodity) | 3 | $25 | $75 | [Amazon 검색](https://www.amazon.com/s?k=hdmi+splitter+1x2+4k+hdr+hdcp+2.2) · [다나와](https://search.danawa.com/dsearch.php?query=HDMI+분배기+1대2+4K+HDR) |
| 5 | Thunderbolt 4 Dock | **OWC 11-Port** (OWCTB4DOCK, 96W) | 1 | $279 | $279 | [owc.com](https://eshop.macsales.com/shop/owc-thunderbolt-dock) · [Amazon](https://www.amazon.com/OWC-Thunderbolt-Dock-Compatible-Equipped/dp/B097TVLB4F) |
| 6 | Smart Power Plug | **Shelly Plus Plug** (HTTP RPC API) | 3 | $25 | $75 | [shelly.com](https://us.shelly.com/products/shelly-plus-plug-us-2-pack) · [Amazon](https://www.amazon.com/Shelly-Plus-Plug-US-Measurement/dp/B0CK8JBZ3V/) |
| 7 | USB-UART 케이블 | **FTDI TTL-232R-3V3** (정품) | 2 | $15 | $30 | [ftdichip.com](https://ftdichip.com/products/ttl-232r-3v3/) · [Adafruit](https://www.adafruit.com/product/70) |
| 8 | 1U 랙 마운트 | Sonnet xMac mini Server | 1 | $75 | $75 | [Amazon 검색](https://www.amazon.com/s?k=Sonnet+xMac+mini+rackmount) |
| 9 | HDMI Dummy Plug | 4K 헤드리스 (commodity) | 1 | $10 | $10 | [Amazon 검색](https://www.amazon.com/s?k=HDMI+dummy+plug+4K) |
| | | | | **Tier 1 소계** | **$1,350** | **≈ ₩1,823,000** |

## Tier 2: Sprint 1 본격 확장 — 약 $2,039 (₩275만)

| # | 품목 | 모델 (검증) | 수량 | 단가 | 소계 | 공식 / 구매 |
|---|---|---|---|---|---|---|
| 10 | WiFi 6 AP | **UniFi U6-LR** (Long-Range) | 1 | $179 | $179 | [ui.com](https://store.ui.com/us/en/products/u6-lr) · [Amazon](https://www.amazon.com/Ubiquiti-Long-Range-Adapter-Included-U6-LR-US/dp/B08V1PF29L) · [B&H](https://www.bhphotovideo.com/c/product/1610117-REG/ubiquiti_networks_u6_lr_us_unifi_6_long_range_access.html) |
| 11 | 모니터 27" 4K | 운영자 가시화용 (commodity) | 2 | $350 | $700 | (사내 자산 우선) [다나와](https://search.danawa.com/dsearch.php?query=27인치+4K+모니터) |
| 12 | 스튜디오 모니터 스피커 | 5" USB · 음성 시나리오 | 1 | $80 | $80 | [다나와](https://search.danawa.com/dsearch.php?query=스튜디오+모니터+스피커+5인치) |
| 13 | 음성 리모컨 (자사 표준 BT) | BT 5.0 + Voice — *사내 발주* | 2 | $50 | $100 | (사내 펌웨어팀) |
| 14 | BT 헤드폰 P1 (AirPods Pro급) | A2DP + AVRCP — Apple AirPods Pro | 1 | $250 | $250 | [apple.com](https://www.apple.com/shop/buy-airpods/airpods-pro) |
| 15 | BT 헤드폰 P1 (소니) | Sony WH-1000XM5 — A2DP+AVRCP+HSP | 1 | $400 | $400 | [sony.com](https://www.sony.com/electronics/headband-headphones/wh-1000xm5) |
| 16 | OPNsense Mini PC (방화벽) | Mini PC + OPNsense DIY (anomaly_injector) | 1 | $250 | $250 | [opnsense.org](https://opnsense.org/) · [Amazon mini PC](https://www.amazon.com/s?k=opnsense+mini+pc) |
| 17 | 스피커 거치대 + 흡음 폼 | 가변 높이 + 30×30cm 4매 | 1 | $80 | $80 | [다나와](https://search.danawa.com/dsearch.php?query=스튜디오+거치대+흡음) |
| | | | | **Tier 2 소계** | **$2,039** | **≈ ₩2,752,000** |

## Tier 3: Sprint 2 자동화 (BT 페어링 무인) — 약 $115 (₩16만)

| # | 품목 | 모델 | 수량 | 단가 | 소계 | URL |
|---|---|---|---|---|---|---|
| 18 | Raspberry Pi 4 (4GB) | + 케이스 + SD 32GB | 1 | $80 | $80 | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) |
| 19 | SG90/MG90S 서보모터 | 3개 세트 | 1 | $15 | $15 | [Amazon 검색](https://www.amazon.com/s?k=MG90S+servo+3+pack) |
| 20 | PCA9685 16채널 PWM | I2C | 1 | $10 | $10 | [adafruit.com](https://www.adafruit.com/product/815) |
| 21 | 3D 프린팅 푸셔 헤드 | 디바이스별 5종 (외주 또는 사내) | 5 | $2 | $10 | (사내/외주) |
| | | | | **Tier 3 소계** | **$115** | **≈ ₩155,000** |

### 🏆 최적 효과 합계
- **Tier 1만**: $1,350 ≈ **₩182만** (200 시나리오 화면·IR·네트워크 자동화 시작 가능)
- **Tier 1 + 2**: $3,389 ≈ **₩458만** (Sprint 1 음성·BT·anomaly 본격)
- **Tier 1 + 2 + 3**: $3,504 ≈ **₩473만** (Sprint 2 BT 페어링 무인 자동화까지)

---

# 💰 최소비용 최대효과 — PoC 가치 증명

> **목표**: 채널 Zap E2E 1대로 자동화 동작을 시연. 리더십 결재용 데모. 추후 확장 가능 구조.

## 필수 4 품목 — 약 $401 (₩54만)

| # | 품목 | 모델 | 수량 | 단가 | 소계 | URL |
|---|---|---|---|---|---|---|
| 1 | HDMI 캡처카드 | **Magewell USB Capture HDMI 4K Plus** | **1** | $320 | $320 | [magewell.com](https://www.magewell.com/products/usb-capture-hdmi-4k-plus) · [Amazon](https://www.amazon.com/Magewell-USB-Capture-HDMI-Plus/dp/B0754C5XLW) |
| 2 | IR 송신·학습 | **BroadLink RM4 Mini** | 1 | $26 | $26 | [ebroadlink.com](https://ebroadlink.com/products/broadlink-rm4-mini-universal-remote-wi-fi-ir-control-hub_certified-wwa-work-with-alexa_-black) · [Amazon](https://www.amazon.com/Broadlink-RM4-Universal-Control-Compatible/dp/B07ZSF46BX) |
| 3 | VLAN 스위치 | **TP-Link TL-SG108E** (Easy Smart, 8 GbE) | 1 | $30 | $30 | [tp-link.com](https://www.tp-link.com/us/home-networking/8-port-switch/tl-sg108e/) · [Amazon](https://www.amazon.com/Ethernet-Unmanaged-Shielded-Replacement-TL-SG108E/dp/B00K4DS5KU) |
| 4 | HDMI 분배기 1×2 | 4K HDR (commodity) | 1 | $25 | $25 | [Amazon 검색](https://www.amazon.com/s?k=hdmi+splitter+1x2+4k+hdr) · [다나와](https://search.danawa.com/dsearch.php?query=HDMI+분배기+1대2+4K) |
| | | | | **합계** | **$401** | **≈ ₩541,000** |

## 옵션 (있으면 좋음) — 약 $50 (₩7만)

| # | 품목 | 모델 | 수량 | 단가 | 소계 | URL |
|---|---|---|---|---|---|---|
| 5 | Smart Power Plug | Shelly Plus Plug (수동 리셋 대안) | 1 | $25 | $25 | [shelly.com](https://us.shelly.com/products/shelly-plus-plug-us-2-pack) |
| 6 | USB-UART | CH340 (FTDI 대비 1/3 가격) | 1 | $5 | $5 | [Amazon 검색](https://www.amazon.com/s?k=CH340+USB+UART+3.3V) |
| 7 | HDMI Dummy Plug | 헤드리스용 (commodity) | 1 | $10 | $10 | [Amazon 검색](https://www.amazon.com/s?k=HDMI+dummy+plug+4K) |
| 8 | 추가 HDMI 분배기 | 예비 1개 | 1 | $10 | $10 | (위와 동일) |
| | | | | **옵션 소계** | **$50** | **≈ ₩68,000** |

## 💸 더 줄이려면 (절약 옵션)

| 대체 | 효과 | 절감 | 트레이드오프 |
|---|---|---|---|
| Magewell → **Elgato Cam Link 4K** ($90) | 화질·안정성 살짝 ↓ | -$230 | loop-through 없음, 24/7 가동 시 끊김 가능 |
| Reference STB가 **Android TV** | IR 장치 불필요 (ADB) | -$26 | 해당 STB 필수 |
| Reference STB가 **HDMI-CEC 지원** | IR 장치 불필요 (libcec) | -$26 | 캡처카드 CEC 지원 모델 필요 (Magewell는 미지원) |
| Reference STB가 **RDK 박스** | IR 장치 불필요 (Thunder API) | -$26 | RDK Thunder 활성 필요 |

→ **극단적 최소**: Android TV STB + Elgato Cam Link 4K = **약 $145 (₩20만)** 도 가능 (캡처카드 1 + 분배기 + 스위치).

### 💰 최소비용 합계
- **필수만**: $401 ≈ **₩54만** (4 품목 — 채널 Zap E2E 가동 가능)
- **필수 + 옵션**: $451 ≈ **₩61만** (전원 자동 + 로그 수집 추가)
- **극단적 절약 (Android TV)**: 약 **₩20만~**

---

# 📊 직접 비교

| 항목 | 최적 효과 (Tier 1) | 최소비용 (필수) |
|---|---|---|
| HDMI 캡처카드 | Magewell ×2 ($640) | Magewell ×1 ($320) |
| IR 송신 | BroadLink ×1 ($26) | BroadLink ×1 ($26) |
| 스위치 | TP-Link TL-SG3210 ($140, L2+ 풀 관리형) | TL-SG108E ($30, Easy Smart) |
| HDMI 분배기 | ×3 ($75) | ×1 ($25) |
| TB Dock | OWC TB4 ($279) | 없음 (1 캡처면 Mac mini 직결 OK) |
| Power Plug | ×3 ($75) | 없음/×1 |
| USB-UART | FTDI ×2 ($30) | 없음/CH340 ×1 ($5) |
| 랙 마운트 | $75 | 없음 (데스크탑) |
| HDMI Dummy | $10 | 없음/$10 |
| **합계** | **$1,350** | **$401** |
| 커버 시나리오 | 200 (Ref + DUT 동시) | ~50 (Ref 1대) |

---

# 🧭 발주 결정 가이드

## "어느 쪽을 살까?" 의사결정

```
질문: PoC의 목적이 뭔가?
  ├─ 리더십에 자동화 가능성 입증 + 결재 받기  → 💰 최소비용
  │     → 2주 안에 채널 Zap E2E 데모 → 확장 결재
  │
  └─ 6개월 안에 200 시나리오 야간 회귀 가동       → 🏆 최적 효과
        → Tier 1 ($1,350) 먼저 발주, Tier 2/3는 Sprint 진행하며 추가
```

## 단계적 발주 권장 흐름

1. **Day 1~5**: 최소비용 4 품목 + 1 옵션(Shelly Plug) **즉시 발주** — $426
2. **Week 2~3 (Reference STB 가동 확인 후)**: Tier 1 잔여 추가 — DUT용 Magewell 1대 + OWC TB4 Dock + 분배기 2 + Power Plug 2 + UART 1 + 랙 마운트
3. **Sprint 1 (Week 4~)**: Tier 2 일부 — WiFi AP, 음성 스피커, BT P1 디바이스
4. **Sprint 2 (Week 7~)**: Tier 3 GPIO 푸셔

→ **위험 분산** + **현장 적합성 검증 후 추가 발주**.

---

# ⚠️ 발주 전 확인 (체크리스트)

- [ ] **환율·관세** 재확인 (한국 유통가가 글로벌가보다 낮은 경우 있음 — 다나와 비교 권장)
- [ ] **Shelly Plus Plug**는 미국/EU 콘센트형 — **한국 220V는 변환 어댑터 또는 한국형 IoT 멀티탭(HTTP API 있는 모델)으로 대체** 권장
- [ ] **운영 노트북**의 Thunderbolt 4/5 지원 여부 (OWC Dock 효과)
- [ ] Reference STB가 **Android TV / RDK / HDMI-CEC 중 하나라도** 지원하면 IR 장치(BroadLink) 발주 보류 — 0원 자동화 가능 (docs/18)
- [ ] **모니터·노트북·사무용품**은 사내 자산 우선 확인
- [ ] **부가세·배송비** 별도 — 총 +15~20% 예상

---

# 🔗 검증 출처 (2026-05-29 직접 확인)

- Magewell USB Capture HDMI 4K Plus: <https://www.magewell.com/products/usb-capture-hdmi-4k-plus>
- BroadLink RM4 Mini: <https://ebroadlink.com/products/broadlink-rm4-mini-universal-remote-wi-fi-ir-control-hub_certified-wwa-work-with-alexa_-black>
- TP-Link TL-SG3210: <https://www.tp-link.com/us//service-provider/managed-switch/tl-sg3210/>
- TP-Link TL-SG108E: <https://www.tp-link.com/us/home-networking/8-port-switch/tl-sg108e/>
- OWC Thunderbolt 4 Dock: <https://www.owc.com/solutions/thunderbolt-dock>
- Shelly Plus Plug: <https://us.shelly.com/products/shelly-plus-plug-us-2-pack>
- UniFi U6-LR: <https://store.ui.com/us/en/products/u6-lr>
- Elgato Cam Link 4K: <https://www.elgato.com/us/en/p/cam-link-4k>
- FTDI TTL-232R-3V3: <https://ftdichip.com/products/ttl-232r-3v3/>

관련 문서: [docs/06 환경구성](06-test-environment.md) · [docs/18 저가 대안](18-low-cost-alternatives.md) · [docs/19 견적/품의서](19-procurement-quotation.md) · [docs/procurement-required.html](procurement-required.html) (이전 버전)
