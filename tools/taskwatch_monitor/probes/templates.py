"""Ready-made task templates (registry-entry presets).

Each :class:`TaskTemplate` bundles an adapter + parser + ETA model + notify set
+ required-config keys for a common long-task shape, so a caller can stamp out a
valid :class:`~core.models.TaskSpec` with one call instead of hand-writing the
TOML. Every template's adapter is one of the four the core registry accepts, so
the produced spec round-trips through :func:`core.adapters.adapter_from_spec`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models import TaskSpec


class TemplateError(ValueError):
    """Raised when a template is asked to build a spec with missing config."""


@dataclass(frozen=True)
class TaskTemplate:
    """A preset that stamps out a :class:`TaskSpec` for a task shape."""

    name: str
    adapter: str
    parser: str
    eta_model: str
    notify: tuple[str, ...]
    required_config: tuple[str, ...]
    description: str
    defaults: dict[str, object] = field(default_factory=dict)

    def build(
        self,
        task_id: str,
        config: dict[str, object] | None = None,
        *,
        remediate: bool = False,
    ) -> TaskSpec:
        """Build a :class:`TaskSpec`, merging ``config`` over the defaults.

        Raises :class:`TemplateError` if any ``required_config`` key is absent or
        empty after the merge.
        """
        merged: dict[str, object] = dict(self.defaults)
        if config is not None:
            merged.update(config)
        missing = [key for key in self.required_config if not merged.get(key)]
        if missing:
            raise TemplateError(
                f"template '{self.name}' for task '{task_id}' "
                f"is missing config: {sorted(missing)}"
            )
        return TaskSpec(
            id=task_id,
            adapter=self.adapter,
            parser=self.parser,
            eta_model=self.eta_model,
            notify=list(self.notify),
            remediate=remediate,
            task_type=self.name,
            config=merged,
        )


_TEMPLATE_LIST: tuple[TaskTemplate, ...] = (
    TaskTemplate(
        name="fep-databricks",
        adapter="local-file-tail",
        parser="fep-databricks",
        eta_model="per-phase-weighted",
        notify=("terminal", "first-progress", "stall"),
        required_config=("path",),
        description="Schrodinger FEP+ multisim driver log on Databricks/Modal.",
    ),
    TaskTemplate(
        name="bpmd-modal",
        adapter="local-file-tail",
        parser="bpmd-modal",
        eta_model="ewma-throughput",
        notify=("terminal", "first-progress", "stall"),
        required_config=("path",),
        description="Binding-pose metadynamics driver log (serial trials).",
    ),
    TaskTemplate(
        name="jaguar-qm",
        adapter="local-file-tail",
        parser="jaguar-qm",
        eta_model="ewma-throughput",
        notify=("terminal", "first-progress", "stall"),
        required_config=("path",),
        description="Jaguar QM interaction-energy job set (cluster/ligand/pocket).",
    ),
    TaskTemplate(
        name="modal",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="ewma-throughput",
        notify=("terminal", "stall"),
        required_config=("path",),
        description="Generic Modal app-log tail.",
    ),
    TaskTemplate(
        name="gh-actions-ci",
        adapter="http-json",
        parser="",
        eta_model="per-phase-weighted",
        notify=("terminal", "stall"),
        required_config=("url",),
        description="GitHub Actions run status via the REST API (JSON).",
    ),
    TaskTemplate(
        name="rclone-download",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="ewma-throughput",
        notify=("terminal", "first-progress", "stall"),
        required_config=("path",),
        description="rclone --stats transfer log (percent lines).",
    ),
    TaskTemplate(
        name="npm-build",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="linear-frac",
        notify=("terminal", "stall"),
        required_config=("path",),
        description="npm/webpack build log tail.",
    ),
    TaskTemplate(
        name="cargo-build",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="linear-frac",
        notify=("terminal", "stall"),
        required_config=("path",),
        description="cargo build log tail (Compiling N/M crates).",
    ),
    TaskTemplate(
        name="git-clone",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="ewma-throughput",
        notify=("terminal", "stall"),
        required_config=("path",),
        description="git clone progress log (Receiving objects NN%).",
    ),
    TaskTemplate(
        name="llm-run",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="ewma-throughput",
        notify=("terminal", "first-progress", "stall"),
        required_config=("path",),
        description="LLM generation log (token/step counters).",
    ),
    TaskTemplate(
        name="generic-logfile",
        adapter="local-file-tail",
        parser="generic-logfile",
        eta_model="linear-frac",
        notify=("terminal", "stall"),
        required_config=("path",),
        description="Fallback: any logfile with N/M or percent progress.",
    ),
)

TEMPLATES: dict[str, TaskTemplate] = {tpl.name: tpl for tpl in _TEMPLATE_LIST}


def template_for(name: str) -> TaskTemplate | None:
    """Return the template registered under ``name``, or ``None`` if unknown."""
    return TEMPLATES.get(name)


def build_from_template(
    name: str,
    task_id: str,
    config: dict[str, object] | None = None,
    *,
    remediate: bool = False,
) -> TaskSpec:
    """Build a :class:`TaskSpec` from a named template.

    Raises :class:`TemplateError` for an unknown template name or missing config.
    """
    template = TEMPLATES.get(name)
    if template is None:
        raise TemplateError(
            f"unknown template '{name}'; registered templates are {sorted(TEMPLATES)}"
        )
    return template.build(task_id, config, remediate=remediate)
