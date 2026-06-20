"""Generate authentication flow and API usage diagrams for README."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe


def _rounded_box(ax, x, y, w, h, color, text, fontsize=9, text_color="white", lw=2):
    """Draw a rounded rectangle with centered text."""
    box = mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.15",
        facecolor=color, edgecolor="white", linewidth=lw, zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center", fontsize=fontsize,
        fontweight="bold", color=text_color, zorder=4,
        path_effects=[pe.withStroke(linewidth=0.5, foreground="black")] if text_color == "white" else [],
    )
    return box


def _arrow(ax, x1, y1, x2, y2, label="", color="#5D6D7E", curved=0):
    """Draw an arrow with optional label."""
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=1.8,
            connectionstyle=f"arc3,rad={curved}",
        ),
        zorder=2,
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        offset = 0.2 if curved >= 0 else -0.2
        ax.text(
            mx, my + offset, label,
            ha="center", va="center", fontsize=7.5, color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="#BDC3C7", alpha=0.95),
            zorder=5,
        )


def generate_auth_flow():
    """Generate authentication flow diagram."""
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(-0.5, 14)
    ax.set_ylim(-0.5, 7)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("#F8F9FA")

    # Title
    ax.text(7, 6.6, "Authentication Flow — Azure AD OAuth2 + PKCE",
            ha="center", fontsize=14, fontweight="bold", color="#2C3E50")

    # ── Actors / Components ──
    _rounded_box(ax, 0, 3.5, 2.5, 1.0, "#3498DB", "User\n(Browser)", 10)
    _rounded_box(ax, 5.0, 3.5, 3.0, 1.0, "#2ECC71", "Swagger UI\nlocalhost:8000/docs", 9)
    _rounded_box(ax, 10.5, 3.5, 3.0, 1.0, "#9B59B6", "Azure AD\nlogin.microsoftonline.com", 8)

    _rounded_box(ax, 5.0, 0.5, 3.0, 1.0, "#E67E22", "FastAPI Backend\nlocalhost:8000", 9)
    _rounded_box(ax, 10.5, 0.5, 3.0, 1.0, "#E74C3C", "PostgreSQL\naiapi-postgres:5432", 9)

    # ── Step arrows ──
    # Step 1: User → Swagger
    _arrow(ax, 2.5, 4.0, 5.0, 4.0, "① Open /docs &\nclick Authorize")
    # Step 2: Swagger → Azure AD
    _arrow(ax, 8.0, 4.3, 10.5, 4.3, "② Redirect to\nAzure AD login", curved=0.15)
    # Step 3: Azure AD → Swagger (token)
    _arrow(ax, 10.5, 3.7, 8.0, 3.7, "③ Return JWT\naccess_token", curved=0.15)
    # Step 4: Swagger → FastAPI
    _arrow(ax, 6.5, 3.5, 6.5, 1.5, "④ API call with\nBearer token")
    # Step 5: FastAPI → Postgres
    _arrow(ax, 8.0, 1.0, 10.5, 1.0, "⑤ Lookup user\nrole & vehicles")

    # Info boxes
    info_text = (
        "Token Details:\n"
        "• OAuth2 Authorization Code + PKCE\n"
        "• Azure AD v1.0 endpoint\n"
        f"• Audience: api://015029a3-...\n"
        "• Scope: EV.bedeault"
    )
    ax.text(0.5, 1.8, info_text, fontsize=7.5, va="top", color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#EBF5FB", edgecolor="#3498DB", alpha=0.9))

    role_text = (
        "Role-Based Access:\n"
        "• Admin → see all jobs\n"
        "• User → see only own\n"
        "  vehicle jobs"
    )
    ax.text(11.0, 2.5, role_text, fontsize=7.5, va="top", color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FDEDEC", edgecolor="#E74C3C", alpha=0.9))

    plt.tight_layout()
    plt.savefig("docs/auth_flow.png", dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    print("Saved docs/auth_flow.png")
    plt.close()


def generate_api_usage_flow():
    """Generate API usage / predict pipeline flow diagram."""
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(-0.5, 14)
    ax.set_ylim(-1, 9)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("#F8F9FA")

    ax.text(7, 8.5, "API Usage Flow — Predict Pipeline",
            ha="center", fontsize=14, fontweight="bold", color="#2C3E50")

    # ── Step boxes (vertical flow) ──
    box_w, box_h = 4.0, 0.8
    steps = [
        (5.0, 7.2, "#3498DB", "① POST /api/v1/predict\n{\"HDFS_URL\": \"http://...\"}"),
        (5.0, 5.8, "#2ECC71", "② Server returns job_id immediately\n{\"job_id\": \"abc-123\", \"status\": \"pending\"}"),
        (5.0, 4.4, "#E67E22", "③ Background: Load models from HDFS\n(ReadWriteLock — concurrent reads OK)"),
        (5.0, 3.0, "#9B59B6", "④ Background: Run XGBoost + PyTorch\nensemble on GPU for each vehicle"),
        (5.0, 1.6, "#E74C3C", "⑤ Background: Save results to HDFS\n& persist to PostgreSQL"),
        (5.0, 0.2, "#1ABC9C", "⑥ GET /api/v1/jobs/{job_id}\nPoll until status = \"completed\""),
    ]

    for x, y, color, text in steps:
        _rounded_box(ax, x, y, box_w, box_h, color, text, fontsize=8.5)

    # Arrows between steps
    for i in range(len(steps) - 1):
        x1 = steps[i][0] + box_w / 2
        y1 = steps[i][1]
        y2 = steps[i + 1][1] + box_h
        _arrow(ax, x1, y1, x1, y2, color="#5D6D7E")

    # Side annotations — left
    ax.text(0.3, 7.5, "Client Request", fontsize=9, fontweight="bold", color="#3498DB",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#EBF5FB", edgecolor="#3498DB"))
    _arrow(ax, 2.2, 7.5, 5.0, 7.5, color="#3498DB")

    ax.text(0.3, 6.1, "Non-blocking\nResponse", fontsize=8, fontweight="bold", color="#2ECC71",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#E8F8F5", edgecolor="#2ECC71"))
    _arrow(ax, 5.0, 6.1, 2.3, 6.1, color="#2ECC71")

    # Side annotations — right
    right_x = 10.0
    hdfs_text = "HDFS Cluster\n• Model artifacts\n• CSV results\n• Version control"
    ax.text(right_x, 4.3, hdfs_text, fontsize=7.5, va="top", color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEF9E7", edgecolor="#F39C12", alpha=0.9))
    _arrow(ax, 9.0, 4.7, right_x, 4.5, color="#F39C12")

    gpu_text = "GPU Processing\n• XGBoost gpu_hist\n• PyTorch CUDA\n• Ensemble NN"
    ax.text(right_x, 2.9, gpu_text, fontsize=7.5, va="top", color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#F4ECF7", edgecolor="#9B59B6", alpha=0.9))
    _arrow(ax, 9.0, 3.3, right_x, 3.1, color="#9B59B6")

    db_text = "PostgreSQL\n• sessions table\n• predict_infos table\n• session_vehicles"
    ax.text(right_x, 1.5, db_text, fontsize=7.5, va="top", color="#2C3E50",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FDEDEC", edgecolor="#E74C3C", alpha=0.9))
    _arrow(ax, 9.0, 1.9, right_x, 1.7, color="#E74C3C")

    # Polling annotation
    ax.text(0.3, 0.5, "Client Polling", fontsize=9, fontweight="bold", color="#1ABC9C",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#E8F8F5", edgecolor="#1ABC9C"))
    _arrow(ax, 2.3, 0.5, 5.0, 0.5, color="#1ABC9C")

    plt.tight_layout()
    plt.savefig("docs/api_usage_flow.png", dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    print("Saved docs/api_usage_flow.png")
    plt.close()


if __name__ == "__main__":
    generate_auth_flow()
    generate_api_usage_flow()
