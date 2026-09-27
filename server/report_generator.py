"""Create a PDF report with tables and plots from actual recorded telemetry."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class ReportGenerator:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    @staticmethod
    def _chart(rows: list[dict[str, Any]], series: list[tuple[str, str]], title: str, ylabel: str) -> Drawing:
        """Compact vector line plot - data is the recorded session telemetry."""
        drawing = Drawing(17.2 * cm, 6.15 * cm)
        width, height, margin_left, margin_bottom = 17.2 * cm, 6.15 * cm, 1.25 * cm, .85 * cm
        plot_width, plot_height = width - margin_left - .3 * cm, height - margin_bottom - .65 * cm
        drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=colors.HexColor("#C9D8E0")))
        drawing.add(String(.28 * cm, height - .38 * cm, title, fontName="Helvetica-Bold", fontSize=8.6, fillColor=colors.HexColor("#173A52")))
        drawing.add(String(.28 * cm, height / 2, ylabel, fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#597282"), angle=90))
        drawing.add(String(width - 3.1 * cm, .25 * cm, "Simulation time (s)", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#597282")))
        for index in range(5):
            y = margin_bottom + plot_height * index / 4
            drawing.add(Line(margin_left, y, margin_left + plot_width, y, strokeColor=colors.HexColor("#E4EDF1"), strokeWidth=.35))
        drawing.add(Line(margin_left, margin_bottom, margin_left, margin_bottom + plot_height, strokeColor=colors.HexColor("#567384"), strokeWidth=.55))
        drawing.add(Line(margin_left, margin_bottom, margin_left + plot_width, margin_bottom, strokeColor=colors.HexColor("#567384"), strokeWidth=.55))
        all_values = [float(row.get(field, 0) or 0) for row in rows for field, _ in series]
        low, high = (min(all_values), max(all_values)) if all_values else (0.0, 1.0)
        if abs(high - low) < 1e-9:
            high += 1.0
        palette = [colors.HexColor("#1D8FB3"), colors.HexColor("#E28447"), colors.HexColor("#6E73B8"), colors.HexColor("#36966E")]
        for line_index, (field, label) in enumerate(series):
            values = [float(row.get(field, 0) or 0) for row in rows]
            points: list[float] = []
            for index, value in enumerate(values):
                x = margin_left + plot_width * index / max(1, len(values) - 1)
                y = margin_bottom + plot_height * (value - low) / (high - low)
                points.extend((x, y))
            color = palette[line_index % len(palette)]
            if len(points) >= 4:
                drawing.add(PolyLine(points, strokeColor=color, strokeWidth=1.15))
            legend_x = margin_left + line_index * 3.5 * cm
            drawing.add(Line(legend_x, height - .73 * cm, legend_x + .25 * cm, height - .73 * cm, strokeColor=color, strokeWidth=1.5))
            drawing.add(String(legend_x + .32 * cm, height - .81 * cm, label, fontName="Helvetica", fontSize=6.1, fillColor=colors.HexColor("#4B6473")))
        drawing.add(String(.98 * cm, margin_bottom - .1 * cm, f"{low:.2f}", fontName="Helvetica", fontSize=5.7, fillColor=colors.HexColor("#597282")))
        drawing.add(String(.98 * cm, margin_bottom + plot_height - .1 * cm, f"{high:.2f}", fontName="Helvetica", fontSize=5.7, fillColor=colors.HexColor("#597282")))
        return drawing

    def generate(self, session_id: str, summary: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"{session_id}.pdf"
        document = SimpleDocTemplate(str(path), pagesize=A4, title="FSOC Coarse Alignment Performance Report", rightMargin=1.4 * cm, leftMargin=1.4 * cm, topMargin=1.35 * cm, bottomMargin=1.3 * cm)
        styles = getSampleStyleSheet()
        title, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
        title.textColor = colors.HexColor("#12314A")
        h2.textColor = colors.HexColor("#146C8B")
        body.fontSize, body.leading = 8.5, 11
        story: list[Any] = [Paragraph("FSOC COARSE ALIGNMENT PERFORMANCE REPORT", title), Paragraph("Independent live-simulation session report - values are calculated from recorded session telemetry.", body), Spacer(1, .35 * cm)]
        session = [["Session ID", session_id], ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")], ["Duration", f"{summary.get('duration', 0):.2f} s"], ["Motion", str(config.get("motion", {}).get("pattern", "-"))], ["Active target", str(config.get("lock", {}).get("active_target_id", "-"))]]
        story += [Paragraph("Session information", h2), self._table(session), Spacer(1, .25 * cm)]
        perf = [["Average / min / max FPS", f"{summary.get('average_fps', 0):.2f} / {summary.get('minimum_fps', 0):.2f} / {summary.get('maximum_fps', 0):.2f}"], ["Frames processed / dropped", f"{summary.get('total_frames_processed', 0)} / {summary.get('total_frames_dropped', 0)}"], ["Average / max processing", f"{summary.get('average_processing_time', 0):.3f} / {summary.get('maximum_processing_time', 0):.3f} ms"], ["Average / max tracking error", f"{summary.get('average_tracking_error', 0):.3f} / {summary.get('maximum_tracking_error', 0):.3f} px"], ["Average / max angular error", f"{summary.get('average_angular_error', 0):.3f} / {summary.get('maximum_angular_error', 0):.3f} deg"], ["Average confidence", str(summary.get("average_detection_confidence", 0))], ["Lock / FSOC retention", f"{summary.get('lock_retention_rate', 0):.2f}% / {summary.get('fsoc_link_retention_rate', 0):.2f}%"]]
        story += [Paragraph("System and tracking performance", h2), self._table(perf), Spacer(1, .25 * cm)]
        alignment = [["Acquisition / first lock", f"{summary.get('acquisition_time')} s / {summary.get('time_to_first_lock')} s"], ["Target losses / reacquisitions", f"{summary.get('target_loss_count', 0)} / {summary.get('target_reacquisition_count', 0)}"], ["FOV violations / LOS interruptions", f"{summary.get('fov_violation_count', 0)} / {summary.get('los_interruption_count', 0)}"], ["FOV compliance / LOS availability", f"{summary.get('fov_compliance', 0):.2f}% / {summary.get('los_availability', 0):.2f}%"], ["Total FSOC downtime", f"{summary.get('total_fsoc_link_downtime', 0):.2f} s"], ["Tracking stability", str(summary.get("tracking_stability_metric", 0))]]
        story += [Paragraph("Alignment, FOV, LOS and FSOC", h2), self._table(alignment), Spacer(1, .25 * cm)]
        exposure = summary.get("disturbance_exposure", {})
        dist_rows = [["Platform vibration", str(exposure.get("platform_vibration", {}))], ["Camera motion", str(exposure.get("camera_motion", {}))], ["Atmospheric turbulence", str(exposure.get("atmospheric_turbulence", {}))], ["Sensor noise", str(exposure.get("sensor_noise", {}))], ["Fog / image noise", f"{exposure.get('fog', {})} / {exposure.get('noise', {})}"], ["Jitter / rain", f"{exposure.get('jitter', {})} / {exposure.get('rain', {})}"]]
        story += [Paragraph("Disturbance configuration", h2), self._table(dist_rows), Spacer(1, .35 * cm), Paragraph("Atmospheric turbulence is an image-domain simulation approximation, not a complete optical-propagation model.", body), PageBreak()]
        charts = [("Tracking Error vs Time", [("pixel_error", "Pixel error"), ("angular_error", "Angular error")], "Error"), ("Camera Angle vs Target Angle", [("target_azimuth", "Target azimuth"), ("camera_pan", "Camera pan"), ("target_elevation", "Target elevation"), ("camera_tilt", "Camera tilt")], "Degrees"), ("FPS vs Time", [("fps", "FPS")], "FPS"), ("Processing Time vs Time", [("processing_time_ms", "Processing time")], "Milliseconds"), ("Detection Confidence vs Time", [("confidence", "Confidence")], "Confidence"), ("Disturbance Level vs Tracking Error", [("disturbance_level", "Disturbance level"), ("pixel_error", "Pixel error")], "Level / px")]
        story += [Paragraph("Performance graphs", h2)]
        for title_text, series, ylabel in charts:
            story += [self._chart(rows, series, title_text, ylabel), Spacer(1, .12 * cm)]
        story += [PageBreak(), Paragraph("Session events", h2)]
        event_data = [["Time", "Category", "Event"]] + [[f"{event.get('timestamp', 0):.2f}s", event.get("category", "system"), event.get("message", "")] for event in events[-60:]]
        story.append(self._table(event_data, header=True))
        document.build(story, onFirstPage=self._page, onLaterPages=self._page)
        return path

    @staticmethod
    def _table(rows: list[list[Any]], header: bool = False) -> Table:
        columns = max((len(row) for row in rows), default=2)
        widths = [5.3 * cm, 12.0 * cm] if columns == 2 else [2.1 * cm, 3.0 * cm, 12.2 * cm]
        table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        commands = [("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#CBD9E2")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONT", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7.6), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F7")), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
        if header:
            commands += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12314A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        table.setStyle(TableStyle(commands))
        return table

    @staticmethod
    def _page(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#B8D6E2"))
        canvas.line(document.leftMargin, A4[1] - .8 * cm, A4[0] - document.rightMargin, A4[1] - .8 * cm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#5B7482"))
        canvas.drawString(document.leftMargin, .65 * cm, "FSOC Coarse Alignment - performance report")
        canvas.drawRightString(A4[0] - document.rightMargin, .65 * cm, f"Page {document.page}")
        canvas.restoreState()

    def load_csv(self, session_id: str) -> list[dict[str, Any]]:
        path = self.reports_dir / f"{session_id}.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
