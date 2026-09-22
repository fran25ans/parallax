from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import live_nebius_spend_allowed, nebius_api_key, nebius_project_id


SANDBOX_BASE_URL = "https://api.tokenfactory.nebius.com/sandboxes"
DEFAULT_IMAGE = "busybox:latest"


@dataclass(frozen=True)
class SandboxBranch:
    name: str
    parent_uuid: str
    result_uuid: str
    stdout: str


@dataclass(frozen=True)
class SandboxBranchProof:
    checkpoint_uuid: str
    image: str
    branches: list[SandboxBranch]
    same_parent: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxCounterfactualProof:
    checkpoint_uuid: str
    fixture_sha256: str
    control: dict[str, object]
    counterfactual: dict[str, object]
    same_checkpoint: bool
    single_intervention: str
    proven: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sandbox_smoke_plan() -> list[str]:
    return [
        f"Use immutable image {DEFAULT_IMAGE}",
        "Create one filesystem checkpoint containing timeline=base",
        "Fork branch control from that checkpoint and append timeline=control",
        "Fork branch counterfactual from the same checkpoint and append timeline=counterfactual",
        "Verify both results report the same parent checkpoint UUID",
        "Persist only UUIDs and command output; never persist the API key",
    ]


def ticketshop_sandbox_plan() -> list[str]:
    return [
        "Use python:3.12-slim with the standalone TicketShop fixture",
        "Create one persistent checkpoint containing the fixture and baseline SQLite database",
        "Run a disposable control branch from the checkpoint",
        "Run a disposable response-lost branch from the same checkpoint",
        "Parse branch JSON and apply deterministic invariant PAY-001",
        "Persist a credential-free counterfactual proof",
    ]


def stock_race_sandbox_plan() -> list[str]:
    return [
        "Use python:3.12-slim with the standalone stock-race fixture",
        "Create one persistent checkpoint containing one remaining ticket",
        "Run a disposable sequential control branch from the checkpoint",
        "Run a disposable interleaved-buyer branch from the same checkpoint",
        "Apply deterministic invariant STOCK-001 to both final states",
        "Persist a credential-free counterfactual proof",
    ]


def run_live_sandbox_smoke(output: Path) -> SandboxBranchProof:
    if not live_nebius_spend_allowed():
        raise RuntimeError(
            "Live Nebius execution is disabled. Set "
            "PARALLAX_ALLOW_NEBIUS_SPEND=true for one intentional run."
        )

    try:
        from contree_sdk import ContreeSync
        from contree_sdk.auth import IAMAuth
        from contree_sdk.config import ContreeConfig
        from contree_sdk.sdk.exceptions.api import ForbiddenError
    except ImportError as error:
        raise RuntimeError(
            "Nebius Sandbox support is not installed. Install the 'nebius' extra."
        ) from error

    key = nebius_api_key()
    project_id = nebius_project_id()
    config = ContreeConfig(
        auth=IAMAuth(
            base_url=f"{SANDBOX_BASE_URL}/",
            token=key,
            project_id=project_id,
        ),
        transport_timeout=30.0,
        operation_timeout=120.0,
    )
    contree = ContreeSync(config)
    image = contree.images.use(DEFAULT_IMAGE)
    try:
        checkpoint = image.run(
            shell="mkdir -p /parallax && printf 'timeline=base\\n' > /parallax/state.txt",
            disposable=False,
        ).wait()

        control = checkpoint.run(
            shell="printf 'timeline=control\\n' >> /parallax/state.txt && cat /parallax/state.txt"
        ).wait()
        counterfactual = checkpoint.run(
            shell=(
                "printf 'timeline=counterfactual\\n' >> /parallax/state.txt "
                "&& cat /parallax/state.txt"
            )
        ).wait()
    except ForbiddenError as error:
        raise RuntimeError(
            "The API key is valid for Token Factory but lacks the Sandboxes "
            "'spawn' permission for this project. Enable Sandboxes access in "
            "the Token Factory console before retrying."
        ) from error

    proof = SandboxBranchProof(
        checkpoint_uuid=str(checkpoint.uuid),
        image=DEFAULT_IMAGE,
        branches=[
            SandboxBranch(
                name="control",
                parent_uuid=str(checkpoint.uuid),
                result_uuid=str(control.uuid),
                stdout=control.stdout,
            ),
            SandboxBranch(
                name="counterfactual",
                parent_uuid=str(checkpoint.uuid),
                result_uuid=str(counterfactual.uuid),
                stdout=counterfactual.stdout,
            ),
        ],
        same_parent=True,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof.to_dict(), indent=2) + "\n", encoding="utf-8")
    return proof


def run_live_ticketshop_experiment(output: Path) -> SandboxCounterfactualProof:
    if not live_nebius_spend_allowed():
        raise RuntimeError(
            "Live Nebius execution is disabled. Set "
            "PARALLAX_ALLOW_NEBIUS_SPEND=true for one intentional run."
        )

    try:
        from contree_sdk import ContreeSync
        from contree_sdk.auth import IAMAuth
        from contree_sdk.config import ContreeConfig
        from contree_sdk.sdk.exceptions.api import ForbiddenError
        from contree_sdk.utils.models.file import UploadFileSpec
    except ImportError as error:
        raise RuntimeError(
            "Nebius Sandbox support is not installed. Install the 'nebius' extra."
        ) from error

    from hashlib import sha256
    from pathlib import PurePosixPath

    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "ticketshop" / "sandbox_experiment.py"
    fixture_hash = f"sha256:{sha256(fixture.read_bytes()).hexdigest()}"
    config = ContreeConfig(
        auth=IAMAuth(
            base_url=f"{SANDBOX_BASE_URL}/",
            token=nebius_api_key(),
            project_id=nebius_project_id(),
        ),
        transport_timeout=30.0,
        operation_timeout=120.0,
    )
    contree = ContreeSync(config)
    image = contree.images.use("python:3.12-slim")
    try:
        checkpoint = image.run(
            command="python",
            args=(
                "/parallax/sandbox_experiment.py",
                "prepare",
                "/parallax/ticketshop.sqlite3",
            ),
            files=[
                UploadFileSpec(
                    source=fixture,
                    path=PurePosixPath("/parallax/sandbox_experiment.py"),
                )
            ],
            disposable=False,
        ).wait()
        control_run = checkpoint.run(
            command="python",
            args=(
                "/parallax/sandbox_experiment.py",
                "control",
                "/parallax/ticketshop.sqlite3",
            ),
        ).wait()
        counterfactual_run = checkpoint.run(
            command="python",
            args=(
                "/parallax/sandbox_experiment.py",
                "response-lost",
                "/parallax/ticketshop.sqlite3",
            ),
        ).wait()
    except ForbiddenError as error:
        raise RuntimeError(
            "The API key lacks the Sandboxes 'spawn' permission for this project."
        ) from error

    control = json.loads(control_run.stdout.strip())
    counterfactual = json.loads(counterfactual_run.stdout.strip())
    proven = (
        control.get("invariant") == "PASS"
        and counterfactual.get("invariant") == "FAIL"
        and control.get("payment_count") == 1
        and counterfactual.get("payment_count") == 2
    )
    proof = SandboxCounterfactualProof(
        checkpoint_uuid=str(checkpoint.uuid),
        fixture_sha256=fixture_hash,
        control=control,
        counterfactual=counterfactual,
        same_checkpoint=True,
        single_intervention="response_after_commit=LOST",
        proven=proven,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof.to_dict(), indent=2) + "\n", encoding="utf-8")
    return proof


def run_live_stock_race_experiment(output: Path) -> SandboxCounterfactualProof:
    if not live_nebius_spend_allowed():
        raise RuntimeError(
            "Live Nebius execution is disabled. Set "
            "PARALLAX_ALLOW_NEBIUS_SPEND=true for one intentional run."
        )

    try:
        from contree_sdk import ContreeSync
        from contree_sdk.auth import IAMAuth
        from contree_sdk.config import ContreeConfig
        from contree_sdk.sdk.exceptions.api import ForbiddenError
        from contree_sdk.utils.models.file import UploadFileSpec
    except ImportError as error:
        raise RuntimeError(
            "Nebius Sandbox support is not installed. Install the 'nebius' extra."
        ) from error

    from hashlib import sha256
    from pathlib import PurePosixPath

    fixture = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "ticketshop"
        / "stock_race_experiment.py"
    )
    fixture_hash = f"sha256:{sha256(fixture.read_bytes()).hexdigest()}"
    config = ContreeConfig(
        auth=IAMAuth(
            base_url=f"{SANDBOX_BASE_URL}/",
            token=nebius_api_key(),
            project_id=nebius_project_id(),
        ),
        transport_timeout=30.0,
        operation_timeout=120.0,
    )
    contree = ContreeSync(config)
    image = contree.images.use("python:3.12-slim")
    try:
        checkpoint = image.run(
            command="python",
            args=(
                "/parallax/stock_race_experiment.py",
                "prepare",
                "/parallax/stock.sqlite3",
            ),
            files=[
                UploadFileSpec(
                    source=fixture,
                    path=PurePosixPath("/parallax/stock_race_experiment.py"),
                )
            ],
            disposable=False,
        ).wait()
        control_run = checkpoint.run(
            command="python",
            args=(
                "/parallax/stock_race_experiment.py",
                "control",
                "/parallax/stock.sqlite3",
            ),
        ).wait()
        counterfactual_run = checkpoint.run(
            command="python",
            args=(
                "/parallax/stock_race_experiment.py",
                "race",
                "/parallax/stock.sqlite3",
            ),
        ).wait()
    except ForbiddenError as error:
        raise RuntimeError(
            "The API key lacks the Sandboxes 'spawn' permission for this project."
        ) from error

    control = json.loads(control_run.stdout.strip())
    counterfactual = json.loads(counterfactual_run.stdout.strip())
    proven = (
        control.get("invariant") == "PASS"
        and counterfactual.get("invariant") == "FAIL"
        and control.get("sold_count") == 1
        and counterfactual.get("sold_count") == 2
        and counterfactual.get("available_stock") == -1
    )
    proof = SandboxCounterfactualProof(
        checkpoint_uuid=str(checkpoint.uuid),
        fixture_sha256=fixture_hash,
        control=control,
        counterfactual=counterfactual,
        same_checkpoint=True,
        single_intervention="buyers_after_stock_read=INTERLEAVED",
        proven=proven,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof.to_dict(), indent=2) + "\n", encoding="utf-8")
    return proof
