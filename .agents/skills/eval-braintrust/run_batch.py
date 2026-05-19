#!/usr/bin/env python3
"""
Run multiple Braintrust evals concurrently and produce a durable manifest.

The runner uses a unique BRAINTRUST_EXPERIMENT_NAME per child process so each
result can be resolved deterministically even when runs overlap in time.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SKILL_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = Path(
    os.environ.get("OPENAI_MEMBER_AGENT_ROOT", str(Path.home() / "code" / "openai-member-agent"))
)
DEFAULT_RUNNER = DEFAULT_PROJECT_ROOT / "evaluation" / "runners" / "run_evals.sh"
RESOLVE_SCRIPT = SKILL_DIR / "resolve_experiment.py"
FETCH_SCRIPT = SKILL_DIR / "fetch_events.py"
SAVE_BASELINE_SCRIPT = SKILL_DIR / "save_baseline.py"
AGGREGATE_SCRIPT = SKILL_DIR / "aggregate_runs.py"

SEE_RESULTS_RE = re.compile(r"See results for .*/experiments/(?P<name>[^?\s]+)")
EXPERIMENT_NAME_RE = re.compile(r"test-cases-[A-Za-z0-9._-]+")


@dataclass
class RunSpec:
    index: int
    experiment_name: str
    log_path: str


@dataclass
class RunResult:
    index: int
    experiment_name: str
    log_path: str
    status: str
    exit_code: int
    resolved_experiment_id: str | None = None
    resolved_experiment_name: str | None = None
    events_path: str | None = None
    baseline_path: str | None = None
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "batch"


def build_batch_id(phase: str, tag: str | None, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    parts = ["batch", slug(phase)]
    if tag:
        parts.append(slug(tag))
    parts.append(stamp)
    return "-".join(parts)


def normalize_tag(tag: str | None) -> str | None:
    if tag is None:
        return None
    cleaned = tag.strip()
    if not cleaned or cleaned.lower() == "all":
        return None
    return cleaned


def resolve_python_bin(explicit: str | None = None) -> Path:
    configured = explicit or os.environ.get("EVAL_BRAINTRUST_PYTHON")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate.resolve()
        raise FileNotFoundError(f"Configured Python binary not found: {candidate}")

    candidates = [
        Path(os.environ["PYENV_ROOT"]) / "versions" / "3.12.0" / "bin" / "python3"
        if os.environ.get("PYENV_ROOT")
        else None,
        Path.home() / ".pyenv" / "versions" / "3.12.0" / "bin" / "python3",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()

    discovered = shutil.which("python3")
    if discovered:
        return Path(discovered).resolve()
    raise FileNotFoundError("Could not find a usable python3 binary")


def build_experiment_name(provider: str, phase: str, batch_id: str, index: int) -> str:
    return f"test-cases-{slug(provider)}-{slug(phase)}-{batch_id}-run-{index:02d}"


def parse_experiment_name_from_log(log_text: str) -> str | None:
    see_results = SEE_RESULTS_RE.search(log_text)
    if see_results:
        return see_results.group("name")
    matches = EXPERIMENT_NAME_RE.findall(log_text)
    return matches[-1] if matches else None


def run_command(command: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def load_env_file(env_path: Path, env: dict[str, str]) -> dict[str, str]:
    if not env_path.exists():
        return env
    merged = env.copy()
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        merged.setdefault(key, value)
    return merged


def resolve_experiment(
    experiment_name: str,
    env: dict[str, str],
    project: str,
    python_bin: Path,
) -> tuple[str, str]:
    completed = run_command(
        [
            str(python_bin),
            str(RESOLVE_SCRIPT),
            "--identifier",
            experiment_name,
            "--project",
            project,
        ],
        env,
        SKILL_DIR,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "resolve_experiment.py failed")
    exp_id, resolved_name = completed.stdout.strip().split(maxsplit=1)
    return exp_id, resolved_name


def fetch_events(exp_id: str, output_path: Path, env: dict[str, str], python_bin: Path) -> None:
    completed = run_command(
        [
            str(python_bin),
            str(FETCH_SCRIPT),
            "--exp-id",
            exp_id,
            "--output",
            str(output_path),
        ],
        env,
        SKILL_DIR,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "fetch_events.py failed")


def save_baseline(
    events_path: Path,
    exp_id: str,
    exp_name: str,
    output_path: Path,
    env: dict[str, str],
    python_bin: Path,
) -> None:
    completed = run_command(
        [
            str(python_bin),
            str(SAVE_BASELINE_SCRIPT),
            "--events",
            str(events_path),
            "--exp-id",
            exp_id,
            "--exp-name",
            exp_name,
            "--output",
            str(output_path),
        ],
        env,
        SKILL_DIR,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "save_baseline.py failed")


def aggregate_manifest(
    manifest_path: Path,
    summary_path: Path,
    env: dict[str, str],
    python_bin: Path,
) -> None:
    completed = run_command(
        [
            str(python_bin),
            str(AGGREGATE_SCRIPT),
            "--manifest",
            str(manifest_path),
            "--output",
            str(summary_path),
        ],
        env,
        SKILL_DIR,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "aggregate_runs.py failed")


def git_value(project_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def build_run_specs(output_dir: Path, provider: str, phase: str, batch_id: str, runs: int) -> list[RunSpec]:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    specs: list[RunSpec] = []
    for index in range(1, runs + 1):
        experiment_name = build_experiment_name(provider, phase, batch_id, index)
        specs.append(
            RunSpec(
                index=index,
                experiment_name=experiment_name,
                log_path=str(logs_dir / f"run-{index:02d}.log"),
            )
        )
    return specs


def launch_eval(
    spec: RunSpec,
    runner: Path,
    project_root: Path,
    provider: str,
    tag: str | None,
    extra_args: list[str],
) -> tuple[subprocess.Popen[str], object]:
    env = build_eval_env(
        base_env=os.environ.copy(),
        experiment_name=spec.experiment_name,
        tag=tag,
        project_root=project_root,
    )
    command = [str(runner)]
    if provider == "openai":
        command.append("--openai")
    elif provider == "super":
        command.append("--super")
    command.extend(extra_args)
    log_file = open(spec.log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(project_root),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, log_file


def build_eval_env(
    base_env: dict[str, str],
    experiment_name: str,
    tag: str | None,
    project_root: Path,
) -> dict[str, str]:
    env = base_env.copy()
    env["BRAINTRUST_EXPERIMENT_NAME"] = experiment_name
    env.setdefault("MOCK_SERVICE_URL", "http://127.0.0.1:3001")
    if tag:
        env["BRAINTRUST_TAG_FILTER"] = tag
    evaluation_root = str(project_root / "evaluation")
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{evaluation_root}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else evaluation_root
    )
    return env


def wait_for_runs(
    specs: Iterable[RunSpec],
    runner: Path,
    project_root: Path,
    provider: str,
    tag: str | None,
    parallel: int,
    extra_args: list[str],
) -> list[RunResult]:
    pending = list(specs)
    active: dict[int, tuple[RunSpec, subprocess.Popen[str], object]] = {}
    results: list[RunResult] = []

    while pending or active:
        while pending and len(active) < parallel:
            spec = pending.pop(0)
            process, log_file = launch_eval(spec, runner, project_root, provider, tag, extra_args)
            active[spec.index] = (spec, process, log_file)
            print(f"[batch] started run {spec.index:02d}: {spec.experiment_name}", flush=True)

        finished: list[int] = []
        for index, (spec, process, log_file) in active.items():
            exit_code = process.poll()
            if exit_code is None:
                continue
            log_file.close()
            status = "success" if exit_code == 0 else "failed"
            results.append(
                RunResult(
                    index=spec.index,
                    experiment_name=spec.experiment_name,
                    log_path=spec.log_path,
                    status=status,
                    exit_code=exit_code,
                )
            )
            print(f"[batch] finished run {spec.index:02d} with exit code {exit_code}", flush=True)
            finished.append(index)

        for index in finished:
            active.pop(index, None)

        if active:
            time.sleep(1)

    return sorted(results, key=lambda result: result.index)


def enrich_results(
    results: list[RunResult],
    output_dir: Path,
    env: dict[str, str],
    project: str,
    fetch_artifacts: bool,
    python_bin: Path,
) -> None:
    events_dir = output_dir / "events"
    baselines_dir = output_dir / "baselines"
    if fetch_artifacts:
        events_dir.mkdir(parents=True, exist_ok=True)
        baselines_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        if result.status != "success":
            continue
        log_text = Path(result.log_path).read_text(encoding="utf-8")
        emitted_name = parse_experiment_name_from_log(log_text) or result.experiment_name
        try:
            exp_id, resolved_name = resolve_experiment(emitted_name, env, project, python_bin)
            result.resolved_experiment_id = exp_id
            result.resolved_experiment_name = resolved_name
            if fetch_artifacts:
                events_path = events_dir / f"run-{result.index:02d}.json"
                baseline_path = baselines_dir / f"run-{result.index:02d}.json"
                fetch_events(exp_id, events_path, env, python_bin)
                save_baseline(events_path, exp_id, resolved_name, baseline_path, env, python_bin)
                result.events_path = str(events_path)
                result.baseline_path = str(baseline_path)
        except Exception as exc:  # noqa: BLE001 - preserve exact post-processing failure
            result.status = "postprocess_failed"
            result.error = str(exc)


def write_manifest(
    output_dir: Path,
    batch_id: str,
    phase: str,
    provider: str,
    tag: str | None,
    project: str,
    runs: int,
    parallel: int,
    project_root: Path,
    results: list[RunResult],
    started_at: str,
    completed_at: str,
    summary_path: Path | None,
) -> Path:
    manifest_path = output_dir / "manifest.json"
    data = {
        "schema_version": 1,
        "batch_id": batch_id,
        "phase": phase,
        "provider": provider,
        "tag": tag,
        "project": project,
        "runs_requested": runs,
        "parallelism": parallel,
        "started_at": started_at,
        "completed_at": completed_at,
        "project_root": str(project_root),
        "git_branch": git_value(project_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_sha": git_value(project_root, "rev-parse", "HEAD"),
        "summary_path": str(summary_path) if summary_path else None,
        "runs": [asdict(result) for result in results],
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Braintrust eval batches concurrently")
    parser.add_argument("--phase", choices=["pre", "post", "current"], required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--parallel", type=int)
    parser.add_argument("--tag", default="guardrails")
    parser.add_argument("--provider", choices=["super", "openai"], default="super")
    parser.add_argument("--project", default="OpenAI POC")
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--runner", default=str(DEFAULT_RUNNER))
    parser.add_argument("--python-bin", help="Python binary for shipped post-processing scripts")
    parser.add_argument("--output-dir")
    parser.add_argument("--batch-id")
    parser.add_argument("--skip-artifacts", action="store_true")
    parser.add_argument("runner_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be >= 1")
    if args.parallel is not None and args.parallel < 1:
        parser.error("--parallel must be >= 1")
    return args


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    normalized_tag = normalize_tag(args.tag)
    parallel = min(args.parallel or args.runs, args.runs)
    project_root = Path(args.project_root).expanduser().resolve()
    runner = Path(args.runner).expanduser().resolve()
    try:
        python_bin = resolve_python_bin(args.python_bin)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not runner.exists():
        print(f"Runner not found: {runner}", file=sys.stderr)
        return 2

    batch_id = args.batch_id or build_batch_id(args.phase, normalized_tag)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else Path("/tmp") / batch_id
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = build_run_specs(output_dir, args.provider, args.phase, batch_id, args.runs)

    print(
        json.dumps(
            {
                "batch_id": batch_id,
                "phase": args.phase,
                "provider": args.provider,
                "tag": normalized_tag,
                "runs": args.runs,
                "parallel": parallel,
                "output_dir": str(output_dir),
                "python_bin": str(python_bin),
            },
            indent=2,
        ),
        flush=True,
    )

    results = wait_for_runs(
        specs=specs,
        runner=runner,
        project_root=project_root,
        provider=args.provider,
        tag=normalized_tag,
        parallel=parallel,
        extra_args=args.runner_args,
    )

    env = load_env_file(project_root / ".env", os.environ.copy())
    env.setdefault("MOCK_SERVICE_URL", "http://127.0.0.1:3001")
    enrich_results(
        results=results,
        output_dir=output_dir,
        env=env,
        project=args.project,
        fetch_artifacts=not args.skip_artifacts,
        python_bin=python_bin,
    )

    completed_at = utc_now()
    provisional_manifest = write_manifest(
        output_dir=output_dir,
        batch_id=batch_id,
        phase=args.phase,
        provider=args.provider,
        tag=normalized_tag,
        project=args.project,
        runs=args.runs,
        parallel=parallel,
        project_root=project_root,
        results=results,
        started_at=started_at,
        completed_at=completed_at,
        summary_path=None,
    )

    summary_path: Path | None = None
    if not args.skip_artifacts:
        summary_path = output_dir / "aggregate.json"
        try:
            aggregate_manifest(provisional_manifest, summary_path, env, python_bin)
        except Exception as exc:  # noqa: BLE001 - preserve exact aggregation failure
            print(f"Aggregation failed: {exc}", file=sys.stderr)
            return 1

    manifest_path = write_manifest(
        output_dir=output_dir,
        batch_id=batch_id,
        phase=args.phase,
        provider=args.provider,
        tag=normalized_tag,
        project=args.project,
        runs=args.runs,
        parallel=parallel,
        project_root=project_root,
        results=results,
        started_at=started_at,
        completed_at=completed_at,
        summary_path=summary_path,
    )

    failed = [result for result in results if result.status != "success"]
    print(f"[batch] manifest: {manifest_path}")
    if summary_path:
        print(f"[batch] aggregate: {summary_path}")
    if failed:
        print(f"[batch] {len(failed)} run(s) failed or could not be post-processed", file=sys.stderr)
        return 1
    print("[batch] all runs completed and post-processing succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
