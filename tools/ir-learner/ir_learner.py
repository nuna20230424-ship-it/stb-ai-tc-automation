"""IR codeset 자동 학습 CLI — 운영자 친화적 대화형 도구.

사용 예시:
  # BroadLink RM4 Mini (가장 저렴, 권장)
  python ir_learner.py learn --backend broadlink --host 192.168.1.50 \
      --codeset ref_remote --keys POWER CH_UP CH_DOWN

  # Global Caché iTach iLearner
  python ir_learner.py learn --backend itach --host 10.0.10.20 \
      --codeset vendor_x --keys-from-standard

  # 학습된 키를 즉시 검증 (재송신)
  python ir_learner.py verify --backend broadlink --host 192.168.1.50 \
      --codeset ref_remote --key POWER
"""
from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from backends import make_backend
from codeset import STANDARD_KEYS, Codeset

app = typer.Typer(help="IR codeset 자동 학습 도구")
console = Console()


def _resolve_codeset_path(codeset: str) -> Path:
    """codeset 이름을 ir-mcp가 읽는 경로로 변환."""
    base = Path(__file__).resolve().parents[2] / "infrastructure" / "notebook-gateway" / "data" / "ir-codesets"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{codeset}.json"


@app.command()
def learn(
    backend: str = typer.Option(..., "--backend", "-b", help="broadlink | itach"),
    host: str = typer.Option(..., "--host", "-h", help="장치 IP (BroadLink/iTach)"),
    codeset: str = typer.Option(..., "--codeset", "-c", help="codeset 이름 (예: ref_remote)"),
    keys: list[str] = typer.Option(None, "--keys", "-k", help="학습할 키 목록"),
    keys_from_standard: bool = typer.Option(False, "--keys-from-standard", help="표준 키 카탈로그 사용"),
    timeout_sec: int = typer.Option(30, "--timeout", help="키별 대기 시간(초)"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="이미 학습된 키 건너뛰기"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="학습 직후 송신 검증"),
):
    """대화형으로 키를 하나씩 학습 → codeset JSON 저장."""
    target_keys = keys or (STANDARD_KEYS if keys_from_standard else None)
    if not target_keys:
        console.print("[red]키를 지정하세요. --keys 또는 --keys-from-standard[/red]")
        raise typer.Exit(1)

    path = _resolve_codeset_path(codeset)
    cs = Codeset(path)
    cs.meta["backend"] = backend
    cs.meta["host"] = host

    console.print(f"\n[bold cyan]IR codeset 학습 시작[/bold cyan]")
    console.print(f"  백엔드: {backend} @ {host}")
    console.print(f"  대상 codeset: {path}")
    console.print(f"  학습할 키: {len(target_keys)}개")
    if cs.codes:
        console.print(f"  이미 등록된 키: {len(cs.codes)}개")

    if not Confirm.ask("\n시작할까요?", default=True):
        raise typer.Exit(0)

    try:
        be = make_backend(backend, host=host)
    except Exception as e:
        console.print(f"[red]백엔드 초기화 실패: {e}[/red]")
        raise typer.Exit(2)

    learned = 0
    skipped = 0
    failed: list[str] = []

    for i, key in enumerate(target_keys, 1):
        if skip_existing and cs.get(key):
            console.print(f"[dim][{i}/{len(target_keys)}] {key} — 이미 등록됨, 건너뜀[/dim]")
            skipped += 1
            continue

        console.print(f"\n[bold yellow][{i}/{len(target_keys)}] 리모컨의 [{key}] 버튼을 누르세요…[/bold yellow]")
        try:
            be.enter_learning_mode()
            code = be.wait_for_code(timeout_sec=timeout_sec)
        except TimeoutError:
            console.print(f"[red]  시간 초과 — {key} 건너뜀[/red]")
            failed.append(key)
            continue
        except Exception as e:
            console.print(f"[red]  학습 실패: {e}[/red]")
            failed.append(key)
            continue

        cs.set(key, code)
        cs.save()  # 키 하나씩 즉시 저장 (중간에 끊겨도 손실 방지)
        console.print(f"[green]  ✓ 캡처 완료 ({len(code)} chars)[/green]")
        learned += 1

        if verify:
            time.sleep(0.5)
            try:
                be.send(code)
                console.print(f"[dim]  ↺ 검증 송신 OK — STB가 반응하는지 확인하세요[/dim]")
            except Exception as e:
                console.print(f"[yellow]  검증 송신 실패: {e}[/yellow]")
            time.sleep(0.5)

    be.close()

    # 결과 요약
    console.print(f"\n[bold]학습 결과[/bold]")
    table = Table(show_header=True)
    table.add_column("항목")
    table.add_column("개수", justify="right")
    table.add_row("성공", f"[green]{learned}[/green]")
    table.add_row("건너뜀", f"[dim]{skipped}[/dim]")
    table.add_row("실패", f"[red]{len(failed)}[/red]")
    table.add_row("합계", str(len(target_keys)))
    console.print(table)
    if failed:
        console.print(f"[red]실패한 키: {', '.join(failed)}[/red]")
    console.print(f"\n저장 위치: {path}")


@app.command()
def verify(
    backend: str = typer.Option(..., "--backend", "-b"),
    host: str = typer.Option(..., "--host", "-h"),
    codeset: str = typer.Option(..., "--codeset", "-c"),
    key: str = typer.Option(..., "--key", "-k", help="송신할 키 이름"),
):
    """저장된 codeset의 특정 키를 재송신하여 STB 반응 확인."""
    path = _resolve_codeset_path(codeset)
    cs = Codeset(path)
    code = cs.get(key)
    if not code:
        console.print(f"[red]{codeset}에 {key} 없음[/red]")
        raise typer.Exit(1)

    be = make_backend(backend, host=host)
    console.print(f"[cyan]{codeset}/{key} 송신…[/cyan]")
    be.send(code)
    be.close()
    console.print(f"[green]✓ 송신 완료. STB 반응을 확인하세요.[/green]")


@app.command()
def status(
    codeset: str = typer.Option(..., "--codeset", "-c"),
):
    """codeset의 학습 진행 상태 확인."""
    path = _resolve_codeset_path(codeset)
    cs = Codeset(path)
    missing = cs.missing_standard_keys()

    console.print(f"\n[bold]{codeset}[/bold] @ {path}")
    console.print(f"등록된 키: {len(cs.codes)} / 표준 카탈로그: {len(STANDARD_KEYS)}")
    if cs.meta:
        console.print(f"메타: {cs.meta}")
    if missing:
        console.print(f"[yellow]누락된 표준 키 ({len(missing)}): {', '.join(missing[:15])}{'…' if len(missing)>15 else ''}[/yellow]")
    else:
        console.print(f"[green]표준 키 모두 등록 완료[/green]")


if __name__ == "__main__":
    app()
