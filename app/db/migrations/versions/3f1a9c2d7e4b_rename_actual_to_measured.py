"""renomeia csv_actual_predicted para csv_measured_predicted

Revision ID: 3f1a9c2d7e4b
Revises: b807f700b25c
Create Date: 2026-10-03

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f1a9c2d7e4b"
down_revision: str | Sequence[str] | None = "b807f700b25c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# O autogenerate não enxerga mudança em CHECK, então a troca é escrita à mão.
def upgrade() -> None:
    op.drop_constraint(op.f("ck_artifacts_type_valid"), "artifacts", type_="check")
    op.execute(
        "UPDATE artifacts SET type = 'csv_measured_predicted' "
        "WHERE type = 'csv_actual_predicted'"
    )
    op.create_check_constraint(
        op.f("ck_artifacts_type_valid"),
        "artifacts",
        "type IN ('csv_measured_predicted', 'plot_measured_predicted', 'plot_residuals')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_artifacts_type_valid"), "artifacts", type_="check")
    op.execute(
        "UPDATE artifacts SET type = 'csv_actual_predicted' "
        "WHERE type = 'csv_measured_predicted'"
    )
    op.create_check_constraint(
        op.f("ck_artifacts_type_valid"),
        "artifacts",
        "type IN ('csv_actual_predicted', 'plot_measured_predicted', 'plot_residuals')",
    )
