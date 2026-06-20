"""Generate an ER diagram image for the AIAPI database schema using matplotlib."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Table definitions: (name, columns) ──
# Each column: (name, type, constraint_icon)
#   constraint_icon: "PK", "FK", "" (none)

TABLES = {
    "users": {
        "color": "#4A90D9",
        "columns": [
            ("user_id", "VARCHAR", "PK"),
            ("user_name", "VARCHAR", ""),
            ("pw", "VARCHAR", ""),
            ("phone_number", "VARCHAR", ""),
            ("role", "VARCHAR", ""),
        ],
    },
    "vehicles": {
        "color": "#50B86C",
        "columns": [
            ("car_id", "VARCHAR", "PK"),
            ("vehicle_name", "VARCHAR", ""),
            ("vin_number", "VARCHAR", ""),
            ("license_plate", "VARCHAR", ""),
            ("battery_serial", "VARCHAR", ""),
            ("motor_serial", "VARCHAR", ""),
            ("user_id", "VARCHAR", "FK"),
        ],
    },
    "sessions": {
        "color": "#E8833A",
        "columns": [
            ("job_id", "VARCHAR", "PK"),
            ("job_type", "VARCHAR", ""),
            ("user_id", "VARCHAR", "FK"),
            ("status", "VARCHAR", ""),
            ("message", "VARCHAR", ""),
            ("progress", "VARCHAR", ""),
            ("hdfs_url", "VARCHAR", ""),
            ("created_at", "VARCHAR", ""),
            ("started_at", "VARCHAR", ""),
            ("completed_at", "VARCHAR", ""),
            ("result_csv_directory", "VARCHAR", ""),
            ("models_loaded_from", "VARCHAR", ""),
            ("metrics", "JSON", ""),
            ("saved_files", "JSON", ""),
            ("error", "VARCHAR", ""),
        ],
    },
    "session_vehicles": {
        "color": "#9B59B6",
        "columns": [
            ("job_id", "VARCHAR", "PK,FK"),
            ("car_id", "VARCHAR", "PK,FK"),
        ],
    },
    "predict_infos": {
        "color": "#E74C3C",
        "columns": [
            ("car_id", "VARCHAR", "PK,FK"),
            ("session_id", "VARCHAR", "PK,FK"),
            ("max_mileage_km", "VARCHAR", ""),
            ("prediction_method", "VARCHAR", ""),
            ("gt_capacity", "VARCHAR", ""),
            ("pred_xgboost_chg", "VARCHAR", ""),
            ("pred_xgboost_drv", "VARCHAR", ""),
            ("final_ensemble_pred", "VARCHAR", ""),
            ("error", "VARCHAR", ""),
            ("time_stamp", "TIMESTAMP", ""),
        ],
    },
}

# ── Layout positions (x, y) for each table ──
POSITIONS = {
    "users":            (0.5, 8.0),
    "vehicles":         (5.5, 8.0),
    "sessions":         (0.5, 0.5),
    "session_vehicles": (5.5, 4.0),
    "predict_infos":    (10.5, 4.0),
}

TABLE_WIDTH = 3.8
ROW_HEIGHT = 0.32
HEADER_HEIGHT = 0.45
FONT_SIZE = 8
HEADER_FONT_SIZE = 9

# ── Relationship lines ──
RELATIONSHIPS = [
    # (from_table, from_col, to_table, to_col, label)
    ("vehicles",        "user_id",    "users",            "user_id",  "N:1"),
    ("sessions",        "user_id",    "users",            "user_id",  "N:1"),
    ("session_vehicles","job_id",     "sessions",         "job_id",   "N:1"),
    ("session_vehicles","car_id",     "vehicles",         "car_id",   "N:1"),
    ("predict_infos",   "car_id",     "vehicles",         "car_id",   "N:1"),
    ("predict_infos",   "session_id", "sessions",         "job_id",   "N:1"),
]


def draw_table(ax, name, info, x, y):
    """Draw a single table box at (x, y)."""
    cols = info["columns"]
    color = info["color"]
    total_h = HEADER_HEIGHT + len(cols) * ROW_HEIGHT + 0.1

    # Background
    bg = mpatches.FancyBboxPatch(
        (x, y), TABLE_WIDTH, total_h,
        boxstyle="round,pad=0.05", linewidth=1.5,
        edgecolor=color, facecolor="white", zorder=2,
    )
    ax.add_patch(bg)

    # Header
    header = mpatches.FancyBboxPatch(
        (x, y + total_h - HEADER_HEIGHT), TABLE_WIDTH, HEADER_HEIGHT,
        boxstyle="round,pad=0.05", linewidth=0,
        facecolor=color, zorder=3,
    )
    ax.add_patch(header)
    ax.text(
        x + TABLE_WIDTH / 2, y + total_h - HEADER_HEIGHT / 2,
        name, ha="center", va="center",
        fontsize=HEADER_FONT_SIZE, fontweight="bold", color="white", zorder=4,
    )

    # Columns
    col_positions = {}
    for i, (col_name, col_type, constraint) in enumerate(cols):
        row_y = y + total_h - HEADER_HEIGHT - (i + 1) * ROW_HEIGHT
        col_positions[col_name] = (x, row_y, x + TABLE_WIDTH, row_y + ROW_HEIGHT)

        # Constraint badge
        badge = ""
        if "PK" in constraint and "FK" in constraint:
            badge = "PK FK"
            badge_color = "#8E44AD"
        elif "PK" in constraint:
            badge = "PK"
            badge_color = "#2C3E50"
        elif "FK" in constraint:
            badge = "FK"
            badge_color = "#7F8C8D"
        else:
            badge_color = None

        text_x = x + 0.1
        if badge:
            ax.text(
                text_x, row_y + ROW_HEIGHT / 2, badge,
                ha="left", va="center", fontsize=6, fontweight="bold",
                color="white", zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=badge_color, edgecolor="none"),
            )
            text_x += 0.55 if "PK FK" in badge else 0.35

        ax.text(
            text_x, row_y + ROW_HEIGHT / 2, col_name,
            ha="left", va="center", fontsize=FONT_SIZE, color="#2C3E50", zorder=4,
        )
        ax.text(
            x + TABLE_WIDTH - 0.1, row_y + ROW_HEIGHT / 2, col_type,
            ha="right", va="center", fontsize=FONT_SIZE - 1, color="#95A5A6", zorder=4,
        )

    return col_positions


def get_connection_point(col_rect, side):
    """Get (x, y) connection point on left or right side of a column row."""
    x1, y1, x2, y2 = col_rect
    cy = (y1 + y2) / 2
    if side == "left":
        return x1, cy
    return x2, cy


def draw_relationship(ax, from_rect, to_rect, label):
    """Draw a relationship line between two column rects with a label."""
    fx1, fy1, fx2, fy2 = from_rect
    tx1, ty1, tx2, ty2 = to_rect
    fcx = (fx1 + fx2) / 2
    tcx = (tx1 + tx2) / 2

    # Decide sides
    if fcx < tcx:
        start = get_connection_point(from_rect, "right")
        end = get_connection_point(to_rect, "left")
    else:
        start = get_connection_point(from_rect, "left")
        end = get_connection_point(to_rect, "right")

    mid_x = (start[0] + end[0]) / 2
    ax.annotate(
        "", xy=end, xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            color="#7F8C8D",
            lw=1.2,
            connectionstyle=f"arc3,rad=0.1",
        ),
        zorder=1,
    )
    mid_y = (start[1] + end[1]) / 2
    ax.text(
        mid_x, mid_y + 0.15, label,
        ha="center", va="bottom", fontsize=6, color="#7F8C8D",
        bbox=dict(boxstyle="round,pad=0.1", facecolor="white", edgecolor="#BDC3C7", alpha=0.9),
        zorder=5,
    )


def main():
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(-0.5, 15.5)
    ax.set_ylim(-0.5, 12.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(
        7.75, 12.0, "AIAPI Database Schema",
        ha="center", va="center", fontsize=16, fontweight="bold", color="#2C3E50",
    )
    ax.text(
        7.75, 11.5, "PostgreSQL  |  SQLAlchemy 2.0 ORM  |  5 Tables",
        ha="center", va="center", fontsize=10, color="#7F8C8D",
    )

    # Draw tables
    all_col_positions = {}
    for tname, tinfo in TABLES.items():
        x, y = POSITIONS[tname]
        col_pos = draw_table(ax, tname, tinfo, x, y)
        all_col_positions[tname] = col_pos

    # Draw relationships
    for from_t, from_c, to_t, to_c, label in RELATIONSHIPS:
        from_rect = all_col_positions[from_t][from_c]
        to_rect = all_col_positions[to_t][to_c]
        draw_relationship(ax, from_rect, to_rect, label)

    # Legend
    legend_y = 0.2
    for tname, tinfo in TABLES.items():
        ax.add_patch(mpatches.Rectangle((11.0, legend_y), 0.3, 0.25, facecolor=tinfo["color"], edgecolor="none"))
        ax.text(11.45, legend_y + 0.12, tname, fontsize=8, va="center", color="#2C3E50")
        legend_y += 0.35

    plt.tight_layout()
    plt.savefig("docs/db_schema.png", dpi=150, bbox_inches="tight", facecolor="white")
    print("Saved docs/db_schema.png")


if __name__ == "__main__":
    main()
